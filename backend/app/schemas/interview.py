from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class InterviewFilters(BaseModel):
    topics: list[str] = []
    board: str | None = None
    daf: str | None = Field(default=None, max_length=2000)
    source: Literal["auto", "past", "current"] = "auto"


class NextRequest(BaseModel):
    session_id: UUID | None = None
    filters: InterviewFilters


class AnswerRequest(BaseModel):
    session_id: UUID
    answer: str = Field(min_length=1, max_length=6000)
    mode: Literal["coach", "exam"] = "coach"
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
    turn: Turn


class AnswerResponse(BaseModel):
    evaluation: dict[str, Any]
    next: Turn


class TopicInfo(BaseModel):
    name: str
    source: str
    past_questions: int
    recent_articles: int
