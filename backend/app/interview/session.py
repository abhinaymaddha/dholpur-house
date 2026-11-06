"""One interview conversation: asks main questions, evaluates answers, decides follow-ups, reports.

The rules live here, not in the prompts: an answer earns a follow-up only if the evaluator rates it
good (every score at least 3, average at least 3.5), and a main question gets at most MAX_FOLLOWUPS.

To keep the candidate from waiting on the model: the next main question is written while they answer
the current one, and in Exam mode, where feedback is hidden until the report, they wait only for a
quick follow-up decision while the full critique is written in the background.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from uuid import UUID

from app.errors import InterviewError
from app.interview import board, evaluator, prompts
from app.interview.background import BackgroundWork
from app.interview.bank import QuestionBank
from app.interview.questions import QuestionContext, QuestionSource
from app.repositories import InterviewRepository

logger = logging.getLogger(__name__)

MAX_FOLLOWUPS = 2
RETRY_DELAYS = (10, 30)   # seconds before retrying a background evaluation (free models hit rate limits)


@dataclass
class Filters:
    """The candidate's current choices; they can change between questions."""

    topics: list[str]
    board: str | None = None
    daf: str | None = None
    question_mode: str = "generated"   # or "real": past questions only
    plan: str = "full"                 # the board picks the topics; or "topics": the candidate's chosen topics
    length: int = 10                   # main questions in a full interview

    def key(self, main_index: int) -> tuple:
        """Identifies a prepared question: it is only valid for the same question and the same choices."""
        return (main_index, tuple(self.topics), self.board, (self.daf or "").strip(), self.question_mode, self.plan,
                self.length)


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


def _member(src: dict) -> dict:
    """A follow-up comes from the board member who asked the main question."""
    return {"asked_by": src["asked_by"]} if src.get("asked_by") else {}


def _exchange(chain: list[dict], latest_id: int, text: str) -> str:
    return "\n\n".join(
        f"Board{' (follow-up)' if t['depth'] else ''}: {t['question']}\n"
        f"Candidate: {t['answer'] if t['id'] != latest_id else text}"
        for t in chain if t["answer"] or t["id"] == latest_id)


class InterviewSession:

    def __init__(self, session_id: UUID, repo: InterviewRepository, bank: QuestionBank,
                 sources: dict[str, QuestionSource], background: BackgroundWork | None = None):
        self.id = session_id
        self.repo = repo
        self.bank = bank
        self.sources = sources
        self.background = background    # None: everything runs within the request

    @classmethod
    def open(cls, session_id: UUID | None, repo: InterviewRepository, bank: QuestionBank,
             sources: dict[str, QuestionSource], background: BackgroundWork | None = None) -> InterviewSession:
        """Resume a session, or start a new one when the id is missing or unknown."""
        if not (session_id and repo.session_exists(session_id)):
            session_id = repo.create_session()
        return cls(session_id, repo, bank, sources, background)

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

    def next_question(self, filters: Filters) -> dict | None:
        """Ask the next main question with the current filters; None once a full interview is over.
        An unanswered question is marked skipped."""
        turns = self.turns
        for t in turns:
            if _open(t):
                self.repo.mark_skipped(t["id"])
        main_index = max((t["main_index"] for t in turns), default=0) + 1
        if filters.plan == "full" and main_index > filters.length:
            return None
        prepared = self.background.take(self.id, filters.key(main_index)) if self.background else None
        topic, question, src = prepared or self._write(main_index, filters, turns)
        turn = self.repo.add_turn(self.id, main_index, 0, topic, question, src)
        self._prepare_next(main_index + 1, filters, [*turns, turn])
        return turn

    def _write(self, main_index: int, filters: Filters, turns: list[dict]) -> tuple[str, str, dict]:
        """Write a main question: its topic, text and source."""
        daf = (filters.daf or "").strip() or None
        member = None
        if filters.plan == "full":
            slot = board.plan(filters.length, str(self.id), self.bank.topic_counts(), bool(daf))[main_index - 1]
            topic, member = prompts.topics()[slot.topic], slot.member
        else:
            topic = self.pick_topic(filters.topics, main_index)
        if topic.needs_daf and not daf:
            raise InterviewError("Add your DAF details in the filters to be asked DAF-based questions")
        source = self.sources["real" if filters.question_mode == "real" else "generated"]
        question, src = source.next(QuestionContext(topic=topic, board=filters.board, daf=daf, turns=turns))
        return topic.name, question, {**src, "asked_by": member} if member else src

    def _prepare_next(self, main_index: int, filters: Filters, turns: list[dict]) -> None:
        """Write the next main question while the candidate answers this one. Real past questions are found
        quickly without the model, and a follow-up leaves the prepared question waiting for its turn."""
        if not self.background or filters.question_mode == "real":
            return
        if filters.plan == "full" and main_index > filters.length:
            return
        self.background.prepare(self.id, filters.key(main_index), lambda: self._write(main_index, filters, turns))

    def answer(self, text: str, mode: str, filters: Filters, spoken: bool = False) -> dict:
        """Evaluate the answer to the open question; return the evaluation and the next question."""
        turns = self.turns
        pending = next((t for t in reversed(turns) if _open(t)), None)
        if not pending:
            raise InterviewError("There is no open question. Ask for the next question first.")
        chain = [t for t in turns if t["main_index"] == pending["main_index"]]
        exchange = _exchange(chain, pending["id"], text)
        followups_left = MAX_FOLLOWUPS - pending["depth"]
        pairs = []
        if followups_left > 0:
            pairs = [(r["text"], r["follow_up"]) for r in self.bank.similar([pending["question"]], n=12) if r["follow_up"]][:5]
        args = pending["topic"], _context(pending["source"]), _reference(chain), exchange
        if self.background and mode == "exam":
            follow_up = evaluator.decide_follow_up(*args, followups_left, pairs, spoken=spoken) if followups_left > 0 else None
            evaluation = {"pending": True, "spoken": spoken}
            self.repo.save_answer(pending["id"], text, evaluation, mode)
            self._evaluate_later(pending["id"])
        else:
            evaluation, follow_up = evaluator.evaluate(*args, text, followups_left, pairs, spoken=spoken)
            self.repo.save_answer(pending["id"], text, evaluation, mode)
            if evaluation["verdict"] != "good":
                follow_up = None
        if followups_left > 0 and follow_up:
            nxt = self.repo.add_turn(self.id, pending["main_index"], pending["depth"] + 1, pending["topic"],
                                     follow_up, {"type": "followup", **_member(pending["source"])})
        else:
            nxt = self.next_question(filters)
        return {"evaluation": evaluation, "next": nxt}

    def _evaluate_later(self, turn_id: int) -> None:
        self.background.evaluate(turn_id, lambda: self.finish_evaluation(turn_id))

    def finish_evaluation(self, turn_id: int) -> None:
        """Write the full critique of an Exam-mode answer. If the model keeps failing, the turn is marked failed
        rather than left pending, so the report can finish without it."""
        turns = self.turns
        turn = next(t for t in turns if t["id"] == turn_id)
        if not (turn["evaluation"] or {}).get("pending"):
            return                   # finished just before the report asked for it again
        chain = [t for t in turns if t["main_index"] == turn["main_index"] and t["depth"] <= turn["depth"]]
        evaluation: dict = {"failed": True}
        for delay in (*RETRY_DELAYS, None):
            try:
                evaluation, _ = evaluator.evaluate(
                    turn["topic"], _context(turn["source"]), _reference(chain), _exchange(chain, turn_id, turn["answer"]),
                    turn["answer"], 0, [], spoken=turn["evaluation"].get("spoken", False))
                break
            except Exception as e:
                logger.warning("Evaluating turn %s failed: %s", turn_id, e)
                if delay is not None:
                    time.sleep(delay)
        self.repo.save_evaluation(turn_id, evaluation)

    def report(self) -> dict:
        turns = self.turns
        waiting = [t for t in turns if (t["evaluation"] or {}).get("pending")]
        if self.background:
            for t in waiting:        # restarts any evaluation a server restart interrupted
                self._evaluate_later(t["id"])
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
            "pending": len(waiting),
            "failed": sum(1 for t in turns if (t["evaluation"] or {}).get("failed")),
            "skipped": sum(1 for t in turns if (t["evaluation"] or {}).get("skipped")),
            "average": avg(answered),
            "verdicts": {v: sum(1 for t in answered if t["evaluation"]["verdict"] == v) for v in ("good", "partial", "weak")},
            "dimensions": {k: avg(answered, k) for k in evaluator.SCORE_KEYS},
            "topics": [{"topic": k, "answered": len(v), "average": avg(v)} for k, v in by_topic.items()],
            "turns": answered,
        }
