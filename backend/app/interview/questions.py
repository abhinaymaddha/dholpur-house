"""Where the next main question comes from: a QuestionSource strategy.

GeneratedQuestionSource writes a new question with model_2 (topic + DAF + news + similar real
questions); RealQuestionSource asks a real past question chosen by meaning, with no LLM call.
"""

from __future__ import annotations

import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app import llm
from app.errors import InterviewError
from app.ingest.tags import profile_tags
from app.interview import prompts
from app.interview.bank import QuestionBank, fmt, fmt_candidates, readable
from app.services.news import NewsService

QUESTION_MODEL = "model_2"


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


QUESTION_SCHEMA = _obj({
    "question": {"type": "string"},
    "angle": {"type": "string", "enum": ["news", "daf", "topic"]},
    "daf_item": {"type": ["string", "null"]},
    "based_on": {"type": "string"},
    "article_url": {"type": ["string", "null"]},
})

# The angle each generated question takes, chosen in code and rotated so one angle can't dominate.
ANGLES = {
    "daf_link": "Connect ONE DAF item that has not been covered yet to {topic}: ask about the topic through the lens of "
                "the candidate's hometown or state, degree, job or optional subject.",
    "news_daf": "Pick ONE recent news item on {topic} and ask about it in a way that draws on the candidate's "
                "background (their state, field of study or work).",
    "topic": "Ask a straight question on {topic}, the kind any candidate could get. Do not use the DAF this time.",
    "news": "Build the question on ONE recent news item about {topic}.",
    "daf_depth": "Test genuine depth on ONE DAF item not covered yet: the basics of their degree, the real challenges "
                 "of their job, or real understanding of a listed hobby (what it involves, why it matters, what it "
                 "taught them). Test understanding, not memorised trivia; asking for one widely known fact is fine.",
    "daf_admin": "Take ONE DAF item not covered yet and ask how it would matter in their work as an officer, or what "
                 "they would do about a real issue in their home district or state.",
}


def daf_items(daf: str) -> list[str]:
    return [i.strip(" .") for i in re.split(r"[;,\n|]+", daf) if len(i.strip(" .")) > 1]


@dataclass
class QuestionContext:
    """Everything a source needs to pick the next main question."""

    topic: prompts.Topic
    board: str | None
    daf: str | None
    turns: list[dict] = field(default_factory=list)

    @property
    def used_question_ids(self) -> list[int]:
        ids: list[int] = []
        for t in self.turns:
            src = t["source"]
            ids += ([src["question_id"]] if src.get("question_id") else []) + src.get("examples", [])
        return ids

    @property
    def used_urls(self) -> list[str]:
        return [t["source"]["url"] for t in self.turns if t["source"].get("url")]

    @property
    def covered_daf_items(self) -> list[str]:
        return [t["source"]["daf_item"] for t in self.turns if t["source"].get("daf_item")]

    @property
    def asked(self) -> str:
        return "\n".join(f"- {t['question']}" for t in self.turns) or "- (nothing yet)"

    @property
    def asked_on_topic(self) -> int:
        return sum(1 for t in self.turns if t["topic"] == self.topic.name and t["depth"] == 0)


class QuestionSource(ABC):
    def __init__(self, bank: QuestionBank, rng: random.Random | None = None):
        self.bank = bank
        self.rng = rng or random.Random()

    @abstractmethod
    def next(self, ctx: QuestionContext) -> tuple[str, dict]:
        """Return (question text, source metadata stored with the turn)."""

    def queries(self, ctx: QuestionContext) -> list[str]:
        """What to search past questions for: the topic itself, and sometimes the DAF."""
        queries = [f"{ctx.topic.name}. {ctx.topic.testing}"]
        if ctx.daf and (ctx.topic.needs_daf or self.rng.random() < 0.5):
            queries.append(ctx.daf)
        return queries


class RealQuestionSource(QuestionSource):
    """A real past question, chosen by meaning from the closest matches; no LLM call."""

    pool_size = 12

    def next(self, ctx: QuestionContext) -> tuple[str, dict]:
        closest = self.bank.similar(self.queries(ctx), n=25, board=ctx.board, exclude_ids=ctx.used_question_ids,
                                    askable=True)
        if not closest:
            raise InterviewError(f"No past questions found for {ctx.topic.name}")
        q = self.rng.choice(closest[:self.pool_size])   # some variety among the closest matches
        return readable(q["text"]), {"type": "past", "question_id": q["id"], "transcript_id": q["transcript_id"],
                                     "board": q["board"], "cse_year": q["cse_year"], "member": q["member"]}


class GeneratedQuestionSource(QuestionSource):
    """A new question written by model_2. With a DAF, the DAF prompt; otherwise the general one."""

    def __init__(self, bank: QuestionBank, news: NewsService, rng: random.Random | None = None):
        super().__init__(bank, rng)
        self.news = news

    @staticmethod
    def angle(ctx: QuestionContext, has_articles: bool) -> str:
        """Rotate through the angles available for this topic, by how many questions it has had so far."""
        if ctx.topic.needs_daf:
            options = ["daf_depth", "daf_admin"]
        elif ctx.daf:
            options = ["daf_link", "news_daf", "topic"] if has_articles else ["daf_link", "topic"]
        else:
            options = ["news", "topic"] if has_articles else ["topic"]
        return options[ctx.asked_on_topic % len(options)]

    def persona(self, board: str | None) -> str:
        if not board:
            return "A typical UPSC board: a chairperson and four members, courteous but probing."
        return (f"The {board} board. Questions it has asked (any topic), to show its style and tone:\n"
                f"{fmt(self.bank.board_examples(board), with_follow_up=False)}")

    @staticmethod
    def articles_listing(articles: list[dict]) -> str:
        return "\n".join(f"- [{a['published_at']:%d %b}] {a['title']} ({a['source']})\n  {a['summary'][:400]}\n"
                         f"  url: {a['url']}" for a in articles) or "(none for this question)"

    def prompt(self, ctx: QuestionContext, angle: str, articles: list[dict]) -> tuple[str, list[dict]]:
        """The rendered prompt and the example questions it used."""
        topic = ctx.topic
        instruction = ANGLES[angle].format(topic=topic.name)
        exclude = ctx.used_question_ids
        topic_examples = self.bank.similar([f"{topic.name}. {topic.testing}"] + [a["title"] for a in articles[:3]],
                                           n=10 if ctx.daf else 15, board=ctx.board, exclude_ids=exclude)
        if not ctx.daf:
            return prompts.render(
                "question", topic=topic.name, angle_instruction=instruction, guidance=topic.guidance,
                past_questions=fmt(topic_examples), articles=self.articles_listing(articles),
                persona=self.persona(ctx.board), asked=ctx.asked), topic_examples
        items = daf_items(ctx.daf)
        covered = ctx.covered_daf_items
        daf_examples = self.bank.similar([i for i in items if i not in covered][:6] or items[:6], n=12,
                                         exclude_ids=exclude)
        profile = profile_tags(ctx.daf)
        return prompts.render(
            "question_daf", topic=topic.name, angle_instruction=instruction, guidance=topic.guidance,
            daf="\n".join(f"- {i}" for i in items),
            profile="; ".join(f"{k.replace('_tag', '')}: {', '.join(v) if isinstance(v, list) else v}"
                              for k, v in profile.items() if v) or "(not recognised)",
            covered=", ".join(covered) or "none yet",
            daf_questions=fmt(daf_examples), past_questions=fmt(topic_examples),
            similar_candidates=fmt_candidates(self.bank.similar_candidates(ctx.daf)),
            articles=self.articles_listing(articles), persona=self.persona(ctx.board),
            asked=ctx.asked), topic_examples + daf_examples

    def next(self, ctx: QuestionContext) -> tuple[str, dict]:
        articles = self.news.recent([ctx.topic.name], limit=6, exclude_urls=ctx.used_urls) if ctx.topic.news else []
        angle = self.angle(ctx, bool(articles))
        if not angle.startswith("news"):
            articles = []   # keep the model on the chosen angle
        prompt, examples = self.prompt(ctx, angle, articles)
        out = llm.complete_json(QUESTION_MODEL, [{"role": "user", "content": prompt}], QUESTION_SCHEMA, "question")
        src = {"type": "generated", "angle": out["angle"], "target_angle": angle, "based_on": out["based_on"],
               "daf_item": out.get("daf_item"), "examples": [e["id"] for e in examples]}
        article = next((a for a in articles if a["url"] == out.get("article_url")), None)
        if article:
            src |= {"url": article["url"], "title": article["title"], "summary": article["summary"][:600],
                    "publisher": article["source"], "published_at": article["published_at"].isoformat()}
        return out["question"].strip(), src
