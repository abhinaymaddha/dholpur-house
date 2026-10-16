"""SQL for TranscriptFilters, shared by every repository that queries transcripts (alias `t`)."""

from __future__ import annotations

from app.schemas.filters import TranscriptFilters

# filter field -> SQL condition
_CONDITIONS = {
    "board": "t.board = %(board)s",
    "cse_year": "t.cse_year = %(cse_year)s",
    "exam": "t.exam = %(exam)s",
    "background": "%(background)s = ANY(t.background)",
    "optional_tag": "t.optional_tag = %(optional_tag)s",
    "state": "%(state)s = ANY(t.states)",
    "interest": "%(interest)s = ANY(t.interests)",
    "topics": "t.topics @> %(topics)s::text[]",
    "has_marks": "t.pt_marks IS NOT NULL",
}


def filter_sql(f: TranscriptFilters, skip: tuple[str, ...] = (), q: str = "") -> tuple[str, dict]:
    """WHERE clause for the filters (minus `skip`), plus a keyword match on q when given."""
    clauses, params = [], {}
    for field, cond in _CONDITIONS.items():
        value = getattr(f, field)
        if value and field not in skip:
            clauses.append(cond)
            params[field] = value
    if q.strip():
        clauses.append("t.tsv @@ websearch_to_tsquery('english', %(q)s)")
        params["q"] = q.strip()
    return (" AND ".join(clauses) or "TRUE"), params
