"""Interview mode: pick the next question, evaluate answers, and decide follow-ups.

The rules live here, not in the prompt: an answer earns a follow-up only if the evaluator rates it
good (and every score is at least 3), and a main question gets at most MAX_FOLLOWUPS follow-ups.

Model slots (models.toml): model_2 writes new questions; model_3 evaluates and writes follow-ups
(app/interview/evaluator.py).
"""

from __future__ import annotations

import random
import re
from uuid import UUID

from psycopg.types.json import Jsonb

from app.database import pool
from app.interview import bank, evaluator, prompts
from app.interview.evaluator import SCORE_KEYS
from app.services import news
from app.services.llm import complete_json

QUESTION_MODEL = "model_2"
MAX_FOLLOWUPS = 2


class InterviewError(ValueError):
    pass


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


def _angle(topic: prompts.Topic, daf: str | None, has_articles: bool, turns: list[dict]) -> str:
    """Rotate through the angles available for this topic, by how many questions it has had so far."""
    if topic.needs_daf:
        options = ["daf_depth", "daf_admin"]
    elif daf:
        options = ["daf_link", "news_daf", "topic"] if has_articles else ["daf_link", "topic"]
    else:
        options = ["news", "topic"] if has_articles else ["topic"]
    asked_on_topic = sum(1 for t in turns if t["topic"] == topic.name and t["depth"] == 0)
    return options[asked_on_topic % len(options)]


# ---------- sessions and turns ----------

def _turns(conn, session_id: UUID) -> list[dict]:
    return conn.execute(
        "SELECT id, main_index, depth, topic, question, source, answer, evaluation, mode FROM interview_turns"
        " WHERE session_id = %s ORDER BY id", (session_id,)).fetchall()


def _ensure_session(conn, session_id: UUID | None) -> UUID:
    if session_id and conn.execute("SELECT 1 FROM interview_sessions WHERE id = %s", (session_id,)).fetchone():
        return session_id
    return conn.execute("INSERT INTO interview_sessions DEFAULT VALUES RETURNING id").fetchone()["id"]


def _add_turn(conn, session_id: UUID, main_index: int, depth: int, topic: str, question: str, source: dict) -> dict:
    return conn.execute(
        "INSERT INTO interview_turns (session_id, main_index, depth, topic, question, source)"
        " VALUES (%s, %s, %s, %s, %s, %s)"
        " RETURNING id, main_index, depth, topic, question, source, answer, evaluation, mode",
        (session_id, main_index, depth, topic, question, Jsonb(source))).fetchone()


def get_session(session_id: UUID) -> list[dict]:
    with pool.connection() as conn:
        return _turns(conn, session_id)


# ---------- choosing a question ----------

def _pick_topic(chosen: list[str], main_index: int) -> prompts.Topic:
    all_topics = prompts.topics()
    valid = [t for t in chosen if t in all_topics]
    if not valid:
        raise InterviewError("Pick at least one topic to be asked about")
    return all_topics[valid[(main_index - 1) % len(valid)]]   # rotate through the chosen topics


def _persona(board: str | None) -> str:
    if not board:
        return "A typical UPSC board: a chairperson and four members, courteous but probing."
    return (f"The {board} board. Questions it has asked (any topic), to show its style and tone:\n"
            f"{bank.fmt(bank.board_examples(board), with_follow_up=False)}")


def _asked(turns: list[dict]) -> str:
    return "\n".join(f"- {t['question']}" for t in turns) or "- (nothing yet)"


def _used_question_ids(turns: list[dict]) -> list[int]:
    ids = []
    for t in turns:
        src = t["source"]
        ids += ([src["question_id"]] if src.get("question_id") else []) + src.get("examples", [])
    return ids


def _queries(topic: prompts.Topic, daf: str | None, articles: list[dict]) -> list[str]:
    """What to search past questions for: the topic itself, the DAF, and the headlines on offer."""
    queries = [f"{topic.name}. {topic.testing}"]
    if daf and (topic.needs_daf or random.random() < 0.5):
        queries.append(daf)
    queries += [a["title"] for a in articles[:3]]
    return queries


def _articles_listing(articles: list[dict]) -> str:
    return "\n".join(f"- [{a['published_at']:%d %b}] {a['title']} ({a['source']})\n  {a['summary'][:400]}\n  url: {a['url']}"
                     for a in articles) or "(none for this question)"


def _generated_question(topic: prompts.Topic, board: str | None, daf: str | None,
                        turns: list[dict]) -> tuple[str, dict]:
    """A new question written by model_2. With a DAF, the DAF prompt; otherwise the general one."""
    used_urls = [t["source"].get("url") for t in turns if t["source"].get("url")]
    articles = news.recent([topic.name], limit=6, exclude_urls=used_urls) if topic.news else []
    angle = _angle(topic, daf, bool(articles), turns)
    if not angle.startswith("news"):
        articles = []   # keep the model on the chosen angle
    instruction = ANGLES[angle].format(topic=topic.name)
    exclude = _used_question_ids(turns)
    topic_examples = bank.similar([f"{topic.name}. {topic.testing}"] + [a["title"] for a in articles[:3]],
                                  n=10 if daf else 15, board=board, exclude_ids=exclude)

    if daf:
        items = daf_items(daf)
        covered = [t["source"]["daf_item"] for t in turns if t["source"].get("daf_item")]
        daf_examples = bank.similar([i for i in items if i not in covered][:6] or items[:6], n=12, exclude_ids=exclude)
        profile = bank.profile_tags(daf)
        prompt = prompts.render(
            "question_daf", topic=topic.name, angle_instruction=instruction, guidance=topic.guidance,
            daf="\n".join(f"- {i}" for i in items),
            profile="; ".join(f"{k.replace('_tag', '')}: {', '.join(v) if isinstance(v, list) else v}"
                              for k, v in profile.items() if v) or "(not recognised)",
            covered=", ".join(covered) or "none yet",
            daf_questions=bank.fmt(daf_examples), past_questions=bank.fmt(topic_examples),
            similar_candidates=bank.fmt_candidates(bank.similar_candidates(daf)),
            articles=_articles_listing(articles), persona=_persona(board), asked=_asked(turns))
        examples = topic_examples + daf_examples
    else:
        prompt = prompts.render(
            "question", topic=topic.name, angle_instruction=instruction, guidance=topic.guidance,
            past_questions=bank.fmt(topic_examples), articles=_articles_listing(articles),
            persona=_persona(board), asked=_asked(turns))
        examples = topic_examples

    out = complete_json(QUESTION_MODEL, [{"role": "user", "content": prompt}], QUESTION_SCHEMA, "question")
    src = {"type": "generated", "angle": out["angle"], "target_angle": angle, "based_on": out["based_on"],
           "daf_item": out.get("daf_item"), "examples": [e["id"] for e in examples]}
    article = next((a for a in articles if a["url"] == out.get("article_url")), None)
    if article:
        src |= {"url": article["url"], "title": article["title"], "summary": article["summary"][:600],
                "publisher": article["source"], "published_at": article["published_at"].isoformat()}
    return out["question"].strip(), src


def _real_question(topic: prompts.Topic, board: str | None, daf: str | None, turns: list[dict]) -> tuple[str, dict]:
    """A real past question, chosen by meaning (topic, plus DAF when given); no LLM call."""
    closest = bank.similar(_queries(topic, daf, []), n=25, board=board, exclude_ids=_used_question_ids(turns), askable=True)
    if not closest:
        raise InterviewError(f"No past questions found for {topic.name}")
    q = random.choice(closest[:12])   # some variety among the closest matches
    return bank.readable(q["text"]), {"type": "past", "question_id": q["id"], "transcript_id": q["transcript_id"],
                       "board": q["board"], "cse_year": q["cse_year"], "member": q["member"]}


def next_question(session_id: UUID | None, topics: list[str], board: str | None, daf: str | None,
                  question_mode: str = "generated") -> tuple[UUID, dict]:
    """Start the next main question with the current filters (generated, or real past questions only)."""
    with pool.connection() as conn:
        session_id = _ensure_session(conn, session_id)
        turns = _turns(conn, session_id)
        conn.commit()
    pending = [t for t in turns if t["answer"] is None and not (t["evaluation"] or {}).get("skipped")]
    for t in pending:   # an unanswered question is replaced: mark it skipped
        _skip_turn(t["id"])
    main_index = max((t["main_index"] for t in turns), default=0) + 1
    topic = _pick_topic(topics, main_index)
    if topic.needs_daf and not (daf or "").strip():
        raise InterviewError("Add your DAF details in the filters to be asked DAF-based questions")
    daf = (daf or "").strip() or None
    pick = _real_question if question_mode == "real" else _generated_question
    question, src = pick(topic, board, daf, turns)
    with pool.connection() as conn:
        turn = _add_turn(conn, session_id, main_index, 0, topic.name, question, src)
        conn.commit()
    return session_id, turn


def _skip_turn(turn_id: int) -> None:
    with pool.connection() as conn:
        conn.execute("UPDATE interview_turns SET evaluation = %s WHERE id = %s", (Jsonb({"skipped": True}), turn_id))
        conn.commit()


# ---------- answering ----------

def _context(src: dict) -> str:
    """Where the question came from, in a sentence."""
    if src["type"] == "past":
        return f"This is a real question asked in a past interview (CSE {src.get('cse_year')}, {src.get('board')} board)."
    if src["type"] == "generated":
        return f"The board wrote this question for the candidate; it builds on: {src.get('based_on')}."
    if src["type"] == "current":
        return "The question was based on a recent news item (see Reference facts)."
    if src["type"] == "daf":
        return f"This question is about the candidate's DAF item: {src.get('daf_item')}."
    return "This is a follow-up question."


def _reference(chain: list[dict]) -> str:
    """Facts the evaluator may rely on: the news item behind the main question, if any."""
    src = chain[0]["source"]
    if src.get("title"):
        return f"- News item ({src.get('publisher')}, {src.get('published_at', '')[:10]}): {src['title']}. {src.get('summary', '')}"
    return ""


def answer(session_id: UUID, text: str, mode: str, topics: list[str], board: str | None, daf: str | None,
           question_mode: str = "generated") -> dict:
    with pool.connection() as conn:
        turns = _turns(conn, session_id)
    pending = next((t for t in reversed(turns) if t["answer"] is None and not (t["evaluation"] or {}).get("skipped")), None)
    if not pending:
        raise InterviewError("There is no open question. Ask for the next question first.")

    chain = [t for t in turns if t["main_index"] == pending["main_index"]]
    exchange = "\n\n".join(
        f"Board{' (follow-up)' if t['depth'] else ''}: {t['question']}\nCandidate: {t['answer'] if t['id'] != pending['id'] else text}"
        for t in chain if t["answer"] or t["id"] == pending["id"])
    followups_left = MAX_FOLLOWUPS - pending["depth"]
    pairs = [(r["text"], r["follow_up"]) for r in bank.similar([pending["question"]], n=12) if r["follow_up"]][:5]
    evaluation, follow_up = evaluator.evaluate(
        pending["topic"], _context(pending["source"]), _reference(chain), exchange, text, followups_left, pairs)

    with pool.connection() as conn:
        conn.execute("UPDATE interview_turns SET answer = %s, evaluation = %s, mode = %s WHERE id = %s",
                     (text, Jsonb(evaluation), mode, pending["id"]))
        if evaluation["verdict"] == "good" and followups_left > 0 and follow_up:
            nxt = _add_turn(conn, session_id, pending["main_index"], pending["depth"] + 1, pending["topic"],
                            follow_up, {"type": "followup"})
            conn.commit()
            return {"evaluation": evaluation, "next": nxt}
        conn.commit()
    _, nxt = next_question(session_id, topics, board, daf, question_mode)
    return {"evaluation": evaluation, "next": nxt}


# ---------- report ----------

def report(session_id: UUID) -> dict:
    turns = get_session(session_id)
    answered = [t for t in turns if t["answer"] and t["evaluation"] and "scores" in t["evaluation"]]
    by_topic: dict[str, list[dict]] = {}
    for t in answered:
        by_topic.setdefault(t["topic"], []).append(t)

    def avg(ts: list[dict], key: str | None = None) -> float:
        # older evaluations may lack newer dimensions (e.g. tone): average over those that have it
        vals = [t["evaluation"]["average"] if key is None else t["evaluation"]["scores"].get(key) for t in ts]
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    return {
        "answered": len(answered),
        "skipped": sum(1 for t in turns if (t["evaluation"] or {}).get("skipped")),
        "average": avg(answered),
        "verdicts": {v: sum(1 for t in answered if t["evaluation"]["verdict"] == v) for v in ("good", "partial", "weak")},
        "dimensions": {k: avg(answered, k) for k in SCORE_KEYS},
        "topics": [{"topic": k, "answered": len(v), "average": avg(v)} for k, v in by_topic.items()],
        "turns": answered,
    }

