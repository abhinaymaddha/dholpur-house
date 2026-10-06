from pydantic import BaseModel, Field


class Filters(BaseModel):
    board: str | None = None
    cse_year: int | None = None
    exam: str | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    filters: Filters = Filters()
    top_k: int = Field(default=6, ge=1, le=12)
