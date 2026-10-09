"""Interview mode: pick the next question, evaluate answers, and decide follow-ups.

The rules live here, not in the prompt: an answer earns a follow-up only if the evaluator rates it
good (and every score is at least 3), and a main question gets at most MAX_FOLLOWUPS follow-ups.

Model slots (models.toml): model_2 writes new questions, model_3 evaluates and writes follow-ups.
"""

from __future__ import annotations

import random
from datetime import date
from uuid import UUID

from psycopg.types.json import Jsonb

from app.database import pool
from app.interview import bank, prompts
from app.services import news
from app.services.llm import LLMError, complete_json

QUESTION_MODEL = "model_2"
EVALUATION_MODEL = "model_3"
MAX_FOLLOWUPS = 2
SCORE_KEYS = ["relevance", "accuracy", "depth", "balance", "practicality", "clarity"]


class InterviewError(ValueError):
    pass


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


CURRENT_QUESTION_SCHEMA = _obj({"question": {"type": "string"}, "article_url": {"type": "string"}})
DAF_QUESTION_SCHEMA = _obj({"question": {"type": "string"}, "daf_item": {"type": "string"}})
EVALUATION_SCHEMA = _obj({
    "scores": _obj({k: {"type": "integer"} for k in SCORE_KEYS}),
    "verdict": {"type": "string", "enum": ["good", "partial", "weak"]},
    "critique": {"type": "string"},
    "missing_points": {"type": "array", "items": {"type": "string"}},
    "model_answer_points": {"type": "array", "items": {"type": "string"}},
    "follow_up_question": {"type": ["string", "null"]},
})


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


def _source_kind(topic: prompts.Topic, preference: str, daf: str | None) -> str:
    if topic.source == "daf":
        if not daf:
            raise InterviewError("Add your DAF details in the filters to be asked DAF-based questions")
        return "daf"
    if preference == "past":
        return "past"
    if preference == "current":   # only topics configured for current affairs have articles to draw on
        return "current" if topic.source in ("current", "mixed") else "past"
    if topic.source == "current":
        return "current"
    if topic.source == "mixed":
        return "current" if random.random() < topic.current_share else "past"
    return "past"


def _board_style(board: str | None) -> str:
    if not board:
        return ""
    return f"\n## Style of the {board} board\nQuestions this board has asked (any topic):\n{bank.fmt(bank.board_examples(board))}\n"


def _asked(turns: list[dict]) -> str:
    return "\n".join(f"- {t['question']}" for t in turns) or "- (nothing yet)"


def _current_question(topic: prompts.Topic, board: str | None, turns: list[dict]) -> tuple[str, dict] | None:
    used = [t["source"].get("url") for t in turns if t["source"].get("url")]
    articles = news.recent([topic.name], limit=8, exclude_urls=used)
    if not articles:
        return None
    listing = "\n".join(f"- [{a['published_at']:%d %b}] {a['title']} ({a['source']})\n  {a['summary'][:400]}\n  url: {a['url']}"
                        for a in articles)
    prompt = prompts.render("question_current", topic=topic.name, guidance=topic.guidance,
                            past_questions=bank.fmt(bank.examples(topic.name, board)),
                            board_style=_board_style(board), articles=listing, asked=_asked(turns))
    out = complete_json(QUESTION_MODEL, [{"role": "user", "content": prompt}], CURRENT_QUESTION_SCHEMA, "question")
    article = next((a for a in articles if a["url"] == out["article_url"]), articles[0])
    return out["question"], {"type": "current", "url": article["url"], "title": article["title"],
                             "summary": article["summary"][:600],
                             "publisher": article["source"], "published_at": article["published_at"].isoformat()}


def _daf_question(topic: prompts.Topic, board: str | None, daf: str, turns: list[dict]) -> tuple[str, dict]:
    prompt = prompts.render("question_daf", guidance=topic.guidance, daf=daf,
                            past_questions=bank.fmt(bank.examples(topic.name, board, daf=daf)),
                            board_style=_board_style(board), asked=_asked(turns))
    out = complete_json(QUESTION_MODEL, [{"role": "user", "content": prompt}], DAF_QUESTION_SCHEMA, "question")
    return out["question"], {"type": "daf", "daf_item": out["daf_item"]}


def _past_question(topic: prompts.Topic, board: str | None, turns: list[dict]) -> tuple[str, dict]:
    used = [t["source"]["question_id"] for t in turns if t["source"].get("question_id")]
    q = bank.draw(topic.name, board, used)
    if not q:
        raise InterviewError(f"No past questions found for {topic.name}")
    return q["text"], {"type": "past", "question_id": q["id"], "transcript_id": q["transcript_id"],
                       "board": q["board"], "cse_year": q["cse_year"], "member": q["member"]}


def next_question(session_id: UUID | None, topics: list[str], board: str | None, daf: str | None,
                  source: str = "auto") -> tuple[UUID, dict]:
    """Start the next main question with the current filters."""
    with pool.connection() as conn:
        session_id = _ensure_session(conn, session_id)
        turns = _turns(conn, session_id)
        conn.commit()
    pending = [t for t in turns if t["answer"] is None and not (t["evaluation"] or {}).get("skipped")]
    for t in pending:   # an unanswered question is replaced: mark it skipped
        _skip_turn(t["id"])
    main_index = max((t["main_index"] for t in turns), default=0) + 1
    topic = _pick_topic(topics, main_index)
    kind = _source_kind(topic, source, daf)

    result = None
    if kind == "current":
        result = _current_question(topic, board, turns)   # None when no recent articles: fall back to past
    elif kind == "daf":
        result = _daf_question(topic, board, daf or "", turns)
    if result is None:
        result = _past_question(topic, board, turns)
    question, src = result
    with pool.connection() as conn:
        turn = _add_turn(conn, session_id, main_index, 0, topic.name, question, src)
        conn.commit()
    return session_id, turn


def _skip_turn(turn_id: int) -> None:
    with pool.connection() as conn:
        conn.execute("UPDATE interview_turns SET evaluation = %s WHERE id = %s", (Jsonb({"skipped": True}), turn_id))
        conn.commit()


# ---------- answering ----------

def _context(turn: dict) -> str:
    src = turn["source"]
    if src["type"] == "current":
        return (f"The question was based on this recent news item ({src.get('publisher')}, {src.get('published_at', '')[:10]}): "
                f"{src.get('title')}. {src.get('summary', '')}")
    if src["type"] == "past":
        return f"This is a real question asked in a past interview (CSE {src.get('cse_year')}, {src.get('board')} board)."
    if src["type"] == "daf":
        return f"This question is about the candidate's DAF item: {src.get('daf_item')}."
    return "This is a follow-up question."


def answer(session_id: UUID, text: str, mode: str, topics: list[str], board: str | None, daf: str | None,
           source: str = "auto") -> dict:
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
    topic = prompts.topic(pending["topic"])
    pairs = bank.followup_pairs(topic.name)
    instruction = (
        f"If (and only if) the verdict is good, write one follow-up question in `follow_up_question` that probes "
        f"deeper into the candidate's answer: challenge a claim they made, ask for a specific example, or push back "
        f"with a counter-view. One short question, no preamble. Otherwise set it to null. "
        f"(Follow-ups left for this question: {followups_left}.)"
        if followups_left > 0 else "No more follow-ups for this question: set `follow_up_question` to null.")
    prompt = prompts.render(
        "evaluate", topic=topic.name, guidance=topic.guidance, today=date.today().strftime("%d %B %Y"),
        context=_context(pending), exchange=exchange,
        followup_examples="\n".join(f"- Q: {q}\n  Follow-up: {f}" for q, f in pairs) or "- (none found)",
        followup_instruction=instruction)
    evaluation = complete_json(EVALUATION_MODEL, [{"role": "user", "content": prompt}], EVALUATION_SCHEMA, "evaluation")

    # Enforce the rubric in code: "good" needs every score >= 3 and an average >= 3.5.
    scores = {k: max(1, min(5, int(evaluation["scores"].get(k, 1)))) for k in SCORE_KEYS}
    evaluation["scores"] = scores
    evaluation["average"] = round(sum(scores.values()) / len(scores), 2)
    if evaluation["verdict"] == "good" and (min(scores.values()) < 3 or evaluation["average"] < 3.5):
        evaluation["verdict"] = "partial"
    follow_up = evaluation.pop("follow_up_question", None)

    with pool.connection() as conn:
        conn.execute("UPDATE interview_turns SET answer = %s, evaluation = %s, mode = %s WHERE id = %s",
                     (text, Jsonb(evaluation), mode, pending["id"]))
        if evaluation["verdict"] == "good" and followups_left > 0 and follow_up:
            nxt = _add_turn(conn, session_id, pending["main_index"], pending["depth"] + 1, pending["topic"],
                            follow_up.strip(), {"type": "followup"})
            conn.commit()
            return {"evaluation": evaluation, "next": nxt}
        conn.commit()
    _, nxt = next_question(session_id, topics, board, daf, source)
    return {"evaluation": evaluation, "next": nxt}


# ---------- report ----------

def report(session_id: UUID) -> dict:
    turns = get_session(session_id)
    answered = [t for t in turns if t["answer"] and t["evaluation"] and "scores" in t["evaluation"]]
    by_topic: dict[str, list[dict]] = {}
    for t in answered:
        by_topic.setdefault(t["topic"], []).append(t)

    def avg(ts: list[dict], key: str | None = None) -> float:
        vals = [t["evaluation"]["average"] if key is None else t["evaluation"]["scores"][key] for t in ts]
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

