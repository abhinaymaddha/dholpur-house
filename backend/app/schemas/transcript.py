from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TranscriptMeta(BaseModel):
    id: str
    board: str
    alias: str | None
    interview_date: str | None
    daf: str | None
    optional_subject: str | None
    pt_marks: int | None
    exam: str
    cse_year: int
    posted_at: datetime
    telegram_url: str
    background: list[str] = []
    optional_tag: str | None = None
    states: list[str] = []
    interests: list[str] = []
    topics: list[str] = []
    question_count: int = 0


class Transcript(TranscriptMeta):
    text: str
    message_ids: list[int]
    duplicates: list[str]
    structure: dict[str, Any] | None = None


class SearchHit(TranscriptMeta):
    snippet: str
    rank: float | None = None


class SearchResponse(BaseModel):
    total: int
    hits: list[SearchHit]


class FacetCount(BaseModel):
    value: str
    count: int


class Stats(BaseModel):
    transcripts: int
    held: int
    chunks: int
    boards: list[FacetCount]
    years: list[FacetCount]
    exams: list[FacetCount]
    llm_model: str


class YearNode(BaseModel):
    year: int
    count: int
    boards: list[FacetCount]


class Facets(BaseModel):
    total: int
    tree: list[YearNode]
    exam: list[FacetCount]
    background: list[FacetCount]
    optional_tag: list[FacetCount]
    state: list[FacetCount]
    interest: list[FacetCount]
    topic: list[FacetCount]
    has_marks: int
