from pydantic import BaseModel, Field

from app.schemas.filters import TranscriptFilters


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    filters: TranscriptFilters = TranscriptFilters()
    q: str = Field(default="", max_length=300, description="Browse keywords: answer only from matching transcripts")
    top_k: int = Field(default=6, ge=1, le=12)
