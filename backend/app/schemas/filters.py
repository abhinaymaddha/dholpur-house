from fastapi import Query
from pydantic import BaseModel


class TranscriptFilters(BaseModel):
    """Filters shared by search, browse, facets and ask. Empty values mean 'any'."""

    board: str | None = None
    cse_year: int | None = None
    exam: str | None = None
    background: str | None = None
    optional_tag: str | None = None
    state: str | None = None
    interest: str | None = None
    topics: list[str] = []          # all must match
    has_marks: bool = False


def filters_query(
    board: str | None = None,
    cse_year: int | None = None,
    exam: str | None = None,
    background: str | None = None,
    optional_tag: str | None = None,
    state: str | None = None,
    interest: str | None = None,
    topic: list[str] = Query(default=[], description="Repeat for several topics (all must match)"),
    has_marks: bool = False,
) -> TranscriptFilters:
    return TranscriptFilters(board=board, cse_year=cse_year, exam=exam, background=background,
                             optional_tag=optional_tag, state=state, interest=interest, topics=topic,
                             has_marks=has_marks)
