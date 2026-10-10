"""Interview mode: the server asks, the candidate answers, the server evaluates and decides follow-ups."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.database import pool
from app.interview import bank, engine, prompts
from app.schemas.filters import TranscriptFilters
from app.schemas.interview import AnswerRequest, AnswerResponse, NextRequest, NextResponse, TopicInfo, Turn
from app.services.llm import LLMError
from app.services.retrieval import retrieve

router = APIRouter(prefix="/api/interview", tags=["interview"])


def _run(fn, *args):
    try:
        return fn(*args)
    except engine.InterviewError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LLMError as e:
        raise HTTPException(status_code=502, detail=f"The AI model failed: {e}")


@router.get("/topics", response_model=list[TopicInfo])
def list_topics():
    counts = bank.count_by_topic()
    with pool.connection() as conn:
        rows = conn.execute("SELECT unnest(topics) AS t, count(*) AS n FROM news_items GROUP BY 1").fetchall()
    articles = {r["t"]: r["n"] for r in rows}
    return [{"name": t.name, "source": t.source,
             "past_questions": counts.get("Motivation & Personal" if t.source == "daf" else t.name, 0),
             "recent_articles": articles.get(t.name, 0)} for t in prompts.topics().values()]


@router.post("/next", response_model=NextResponse)
def next_question(req: NextRequest):
    """Ask the next main question using the current filters (starts a conversation if needed)."""
    f = req.filters
    session_id, turn = _run(engine.next_question, req.session_id, f.topics, f.board, f.daf, f.source)
    return {"session_id": session_id, "turn": turn}


@router.post("/answer", response_model=AnswerResponse)
def answer(req: AnswerRequest):
    """Evaluate the answer to the open question; returns the evaluation and the next question (follow-up or new)."""
    f = req.filters
    return _run(engine.answer, req.session_id, req.answer, req.mode, f.topics, f.board, f.daf, f.source)


@router.get("/sessions/{session_id}", response_model=list[Turn])
def get_session(session_id: UUID):
    return engine.get_session(session_id)


@router.get("/sessions/{session_id}/report")
def report(session_id: UUID):
    return engine.report(session_id)


@router.get("/turns/{turn_id}/similar")
def similar(turn_id: int):
    """Coach-mode helper: moments in real transcripts closest to this question (no LLM call)."""
    with pool.connection() as conn:
        turn = conn.execute("SELECT question, source FROM interview_turns WHERE id = %s", (turn_id,)).fetchone()
    if not turn:
        raise HTTPException(status_code=404, detail="Unknown question")
    own = turn["source"].get("transcript_id")
    return retrieve(turn["question"], TranscriptFilters(), top_k=4, chunks_per_transcript=1,
                    exclude=(own,) if own else ())
