from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class InterviewFilters(BaseModel):
    topics: list[str] = []
    board: str | None = None
    daf: str | None = Field(default=None, max_length=2000)
    question_mode: Literal["generated", "real"] = "generated"   # real = past questions only, no LLM call
    plan: Literal["full", "topics"] = "full"   # full = the board picks the topics, as in the real interview
    length: Literal[10, 20, 30] = 10           # main questions in a full interview


class NextRequest(BaseModel):
    session_id: UUID | None = None
    filters: InterviewFilters


class AnswerRequest(BaseModel):
    session_id: UUID
    answer: str = Field(min_length=1, max_length=6000)
    mode: Literal["coach", "exam"] = "coach"
    spoken: bool = False   # dictated with speech recognition: the evaluator forgives transcription errors
    filters: InterviewFilters


class Turn(BaseModel):
    id: int
    main_index: int
    depth: int
    topic: str
    question: str
    source: dict[str, Any]
    answer: str | None = None
    evaluation: dict[str, Any] | None = None
    mode: str | None = None


class NextResponse(BaseModel):
    session_id: UUID
    turn: Turn | None          # None: the full interview is over


class AnswerResponse(BaseModel):
    evaluation: dict[str, Any]
    next: Turn | None          # None: the full interview is over


class TopicInfo(BaseModel):
    name: str
    news: bool
    needs_daf: bool
    past_questions: int
    recent_articles: int


class SimilarQuestion(BaseModel):
    id: int
    text: str
    follow_up: str | None
    member: str
    transcript_id: str
    board: str
    cse_year: int
    alias: str | None
