"""Keyword search, filtered listing and facet counts over transcripts (Postgres full-text search)."""

from __future__ import annotations

from app.database import pool
from app.schemas.filters import TranscriptFilters

# Highlight markers that won't occur in transcript text; the UI escapes the snippet and
# swaps these for <mark> tags, so transcript content is never rendered as HTML.
HL_START, HL_END = "⟦", "⟧"
HEADLINE_OPTS = (f"StartSel={HL_START}, StopSel={HL_END}, MaxFragments=3, MaxWords=28, MinWords=10, "
                 "FragmentDelimiter=\" … \"")
META_COLS = ("id, board, alias, interview_date, daf, optional_subject, pt_marks, exam, cse_year, posted_at, "
             "telegram_url, background, optional_tag, states, interests, topics, question_count")

# filter field -> SQL condition (t = transcripts)
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
    """WHERE clause for the filters, plus a keyword match on q when given."""
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


def search(q: str, f: TranscriptFilters, limit: int, offset: int, sort: str = "relevance") -> tuple[int, list[dict]]:
    """Filtered listing; with keywords, matching transcripts with highlighted snippets.

    sort: relevance (keyword rank; newest first without keywords), recent, questions, marks.
    """
    where, params = filter_sql(f)
    params |= {"q": q.strip(), "limit": limit, "offset": offset, "opts": HEADLINE_OPTS}
    order = {"recent": "posted_at DESC", "questions": "question_count DESC, posted_at DESC",
             "marks": "pt_marks DESC NULLS LAST, posted_at DESC"}.get(sort, "posted_at DESC")
    if params["q"] and sort == "relevance":
        order = "rank DESC, posted_at DESC"
    if params["q"]:
        sql = f"""
            WITH query AS (SELECT websearch_to_tsquery('english', %(q)s) AS tsq)
            SELECT {META_COLS},
                   ts_headline('english', text, query.tsq, %(opts)s) AS snippet,
                   ts_rank_cd(tsv, query.tsq) AS rank,
                   count(*) OVER () AS total
            FROM transcripts t, query
            WHERE tsv @@ query.tsq AND {where}
            ORDER BY {order}
            LIMIT %(limit)s OFFSET %(offset)s"""
    else:
        sql = f"""
            SELECT {META_COLS}, left(text, 320) AS snippet, NULL::float AS rank, count(*) OVER () AS total
            FROM transcripts t
            WHERE {where}
            ORDER BY {order}
            LIMIT %(limit)s OFFSET %(offset)s"""
    with pool.connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    total = rows[0]["total"] if rows else 0
    return total, rows


def facets(f: TranscriptFilters, q: str = "") -> dict:
    """Counts for every filter group, within the keyword matches if q is given.

    Each group ignores its own selection, so siblings stay visible.
    """

    def counts(conn, expr: str, skip: tuple[str, ...], array: bool = False) -> list[dict]:
        where, params = filter_sql(f, skip, q)
        value = f"unnest({expr})" if array else expr
        return conn.execute(
            f"SELECT v::text AS value, count(*) AS count FROM (SELECT {value} AS v FROM transcripts t WHERE {where}) x"
            " WHERE v IS NOT NULL GROUP BY v ORDER BY count DESC, value", params).fetchall()

    with pool.connection() as conn:
        where, params = filter_sql(f, ("cse_year", "board"), q)
        tree_rows = conn.execute(
            f"SELECT cse_year, board, count(*) AS count FROM transcripts t WHERE {where}"
            " GROUP BY cse_year, board ORDER BY cse_year DESC, count DESC", params).fetchall()
        where, params = filter_sql(f, ("has_marks",), q)
        with_marks = conn.execute(
            f"SELECT count(*) AS n FROM transcripts t WHERE {where} AND t.pt_marks IS NOT NULL", params).fetchone()["n"]
        where, params = filter_sql(f, q=q)
        total = conn.execute(f"SELECT count(*) AS n FROM transcripts t WHERE {where}", params).fetchone()["n"]
        result = {
            "total": total,
            "exam": counts(conn, "t.exam", ("exam",)),
            "background": counts(conn, "t.background", ("background",), array=True),
            "optional_tag": counts(conn, "t.optional_tag", ("optional_tag",)),
            "state": counts(conn, "t.states", ("state",), array=True),
            "interest": counts(conn, "t.interests", ("interest",), array=True),
            "topic": counts(conn, "t.topics", (), array=True),   # topics combine with AND: narrow within selection
            "has_marks": with_marks,
        }

    tree: dict[int, dict] = {}
    for r in tree_rows:
        year = tree.setdefault(r["cse_year"], {"year": r["cse_year"], "count": 0, "boards": []})
        year["count"] += r["count"]
        year["boards"].append({"value": r["board"], "count": r["count"]})
    result["tree"] = list(tree.values())
    return result
