"""Interview mode: the server asks, the candidate answers, the server evaluates and decides follow-ups."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_bank, get_interviews, get_news, get_question_sources
from app.interview import prompts
from app.interview.bank import QuestionBank
from app.interview.questions import QuestionSource
from app.interview.session import Filters, InterviewSession
from app.repositories import InterviewRepository
from app.schemas.interview import (
    AnswerRequest, AnswerResponse, InterviewFilters, NextRequest, NextResponse, SimilarQuestion, TopicInfo, Turn,
)
from app.services.news import NewsService

router = APIRouter(prefix="/api/interview", tags=["interview"])


def _filters(f: InterviewFilters) -> Filters:
    return Filters(topics=f.topics, board=f.board, daf=f.daf, question_mode=f.question_mode)


class SessionFactory:
    """Opens InterviewSessions with the shared repository, bank and question sources."""

    def __init__(self, repo: InterviewRepository = Depends(get_interviews), bank: QuestionBank = Depends(get_bank),
                 sources: dict[str, QuestionSource] = Depends(get_question_sources)):
        self.repo, self.bank, self.sources = repo, bank, sources

    def open(self, session_id: UUID | None) -> InterviewSession:
        return InterviewSession.open(session_id, self.repo, self.bank, self.sources)


@router.get("/topics", response_model=list[TopicInfo])
def list_topics(bank: QuestionBank = Depends(get_bank), news: NewsService = Depends(get_news)):
    counts, articles = bank.topic_counts(), news.topic_counts()
    return [{"name": t.name, "news": t.news, "needs_daf": t.needs_daf,
             "past_questions": counts.get(t.name, 0), "recent_articles": articles.get(t.name, 0) if t.news else 0}
            for t in prompts.topics().values()]


@router.post("/next", response_model=NextResponse)
def next_question(req: NextRequest, sessions: SessionFactory = Depends()):
    """Ask the next main question using the current filters (starts a conversation if needed)."""
    session = sessions.open(req.session_id)
    return {"session_id": session.id, "turn": session.next_question(_filters(req.filters))}


@router.post("/answer", response_model=AnswerResponse)
def answer(req: AnswerRequest, sessions: SessionFactory = Depends()):
    """Evaluate the answer to the open question; returns the evaluation and the next question (follow-up or new)."""
    return sessions.open(req.session_id).answer(req.answer, req.mode, _filters(req.filters))


@router.get("/sessions/{session_id}", response_model=list[Turn])
def get_session(session_id: UUID, repo: InterviewRepository = Depends(get_interviews)):
    return repo.turns(session_id)


@router.get("/sessions/{session_id}/report")
def report(session_id: UUID, sessions: SessionFactory = Depends()):
    if not sessions.repo.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Unknown interview")
    return sessions.open(session_id).report()


@router.get("/turns/{turn_id}/similar", response_model=list[SimilarQuestion])
def similar(turn_id: int, repo: InterviewRepository = Depends(get_interviews), bank: QuestionBank = Depends(get_bank)):
    """Coach-mode helper: the real past questions closest in meaning to this one, with what was asked next."""
    turn = repo.turn(turn_id)
    if not turn:
        raise HTTPException(status_code=404, detail="Unknown question")
    return bank.similar([turn["question"]], n=5, exclude_transcript=turn["source"].get("transcript_id"))
