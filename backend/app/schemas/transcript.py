from datetime import datetime

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


class Transcript(TranscriptMeta):
    text: str
    message_ids: list[int]
    duplicates: list[str]


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
