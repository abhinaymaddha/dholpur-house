"""One interview conversation: asks main questions, evaluates answers, decides follow-ups, reports.

The rules live here, not in the prompts: an answer earns a follow-up only if the evaluator rates it
good (every score at least 3, average at least 3.5), and a main question gets at most MAX_FOLLOWUPS.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.errors import InterviewError
from app.interview import evaluator, prompts
from app.interview.bank import QuestionBank
from app.interview.questions import QuestionContext, QuestionSource
from app.repositories import InterviewRepository

MAX_FOLLOWUPS = 2


@dataclass
class Filters:
    """The candidate's current choices; they can change between questions."""

    topics: list[str]
    board: str | None = None
    daf: str | None = None
    question_mode: str = "generated"   # or "real": past questions only


def _open(turn: dict) -> bool:
    return turn["answer"] is None and not (turn["evaluation"] or {}).get("skipped")


def _context(src: dict) -> str:
    """Where the question came from, in a sentence (for the evaluator)."""
    if src["type"] == "past":
        return f"This is a real question asked in a past interview (CSE {src.get('cse_year')}, {src.get('board')} board)."
    if src["type"] == "generated":
        return f"The board wrote this question for the candidate; it builds on: {src.get('based_on')}."
    return "This is a follow-up question."


def _reference(chain: list[dict]) -> str:
    """Facts the evaluator may rely on: the news item behind the main question, if any."""
    src = chain[0]["source"]
    if src.get("title"):
        return f"- News item ({src.get('publisher')}, {src.get('published_at', '')[:10]}): {src['title']}. {src.get('summary', '')}"
    return ""


class InterviewSession:

    def __init__(self, session_id: UUID, repo: InterviewRepository, bank: QuestionBank,
                 sources: dict[str, QuestionSource]):
        self.id = session_id
        self.repo = repo
        self.bank = bank
        self.sources = sources

    @classmethod
    def open(cls, session_id: UUID | None, repo: InterviewRepository, bank: QuestionBank,
             sources: dict[str, QuestionSource]) -> InterviewSession:
        """Resume a session, or start a new one when the id is missing or unknown."""
        if not (session_id and repo.session_exists(session_id)):
            session_id = repo.create_session()
        return cls(session_id, repo, bank, sources)

    @property
    def turns(self) -> list[dict]:
        return self.repo.turns(self.id)

    def pending(self) -> dict | None:
        return next((t for t in reversed(self.turns) if _open(t)), None)

    @staticmethod
    def pick_topic(chosen: list[str], main_index: int) -> prompts.Topic:
        all_topics = prompts.topics()
        valid = [t for t in chosen if t in all_topics]
        if not valid:
            raise InterviewError("Pick at least one topic to be asked about")
        return all_topics[valid[(main_index - 1) % len(valid)]]   # rotate through the chosen topics

    def next_question(self, filters: Filters) -> dict:
        """Ask the next main question with the current filters. An unanswered question is marked skipped."""
        turns = self.turns
        for t in turns:
            if _open(t):
                self.repo.mark_skipped(t["id"])
        main_index = max((t["main_index"] for t in turns), default=0) + 1
        topic = self.pick_topic(filters.topics, main_index)
        daf = (filters.daf or "").strip() or None
        if topic.needs_daf and not daf:
            raise InterviewError("Add your DAF details in the filters to be asked DAF-based questions")
        source = self.sources["real" if filters.question_mode == "real" else "generated"]
        question, src = source.next(QuestionContext(topic=topic, board=filters.board, daf=daf, turns=turns))
        return self.repo.add_turn(self.id, main_index, 0, topic.name, question, src)

    def answer(self, text: str, mode: str, filters: Filters) -> dict:
        """Evaluate the answer to the open question; return the evaluation and the next question."""
        turns = self.turns
        pending = next((t for t in reversed(turns) if _open(t)), None)
        if not pending:
            raise InterviewError("There is no open question. Ask for the next question first.")
        chain = [t for t in turns if t["main_index"] == pending["main_index"]]
        exchange = "\n\n".join(
            f"Board{' (follow-up)' if t['depth'] else ''}: {t['question']}\n"
            f"Candidate: {t['answer'] if t['id'] != pending['id'] else text}"
            for t in chain if t["answer"] or t["id"] == pending["id"])
        followups_left = MAX_FOLLOWUPS - pending["depth"]
        pairs = [(r["text"], r["follow_up"]) for r in self.bank.similar([pending["question"]], n=12) if r["follow_up"]][:5]
        evaluation, follow_up = evaluator.evaluate(
            pending["topic"], _context(pending["source"]), _reference(chain), exchange, text, followups_left, pairs)
        self.repo.save_answer(pending["id"], text, evaluation, mode)
        if evaluation["verdict"] == "good" and followups_left > 0 and follow_up:
            nxt = self.repo.add_turn(self.id, pending["main_index"], pending["depth"] + 1, pending["topic"],
                                     follow_up, {"type": "followup"})
        else:
            nxt = self.next_question(filters)
        return {"evaluation": evaluation, "next": nxt}

    def report(self) -> dict:
        turns = self.turns
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
            "dimensions": {k: avg(answered, k) for k in evaluator.SCORE_KEYS},
            "topics": [{"topic": k, "answered": len(v), "average": avg(v)} for k, v in by_topic.items()],
            "turns": answered,
        }
