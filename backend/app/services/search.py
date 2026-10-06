"""Keyword search over whole transcripts with Postgres full-text search."""

from __future__ import annotations

from app.database import pool

# Highlight markers that won't occur in transcript text; the UI escapes the snippet and
# swaps these for <mark> tags, so transcript content is never rendered as HTML.
HL_START, HL_END = "⟦", "⟧"
HEADLINE_OPTS = (f"StartSel={HL_START}, StopSel={HL_END}, MaxFragments=3, MaxWords=28, MinWords=10, "
                 "FragmentDelimiter=\" … \"")
META_COLS = ("id, board, alias, interview_date, daf, optional_subject, pt_marks, exam, cse_year, "
             "posted_at, telegram_url")


def filter_sql(board: str | None, cse_year: int | None, exam: str | None, alias: str = "t") -> tuple[str, dict]:
    clauses, params = [], {}
    if board:
        clauses.append(f"{alias}.board = %(board)s")
        params["board"] = board
    if cse_year:
        clauses.append(f"{alias}.cse_year = %(cse_year)s")
        params["cse_year"] = cse_year
    if exam:
        clauses.append(f"{alias}.exam = %(exam)s")
        params["exam"] = exam
    return (" AND ".join(clauses) or "TRUE"), params


def search(q: str, board: str | None, cse_year: int | None, exam: str | None,
           limit: int, offset: int) -> tuple[int, list[dict]]:
    where, params = filter_sql(board, cse_year, exam)
    params |= {"q": q.strip(), "limit": limit, "offset": offset, "opts": HEADLINE_OPTS}
    if params["q"]:
        sql = f"""
            WITH query AS (SELECT websearch_to_tsquery('english', %(q)s) AS tsq)
            SELECT {META_COLS},
                   ts_headline('english', text, query.tsq, %(opts)s) AS snippet,
                   ts_rank_cd(tsv, query.tsq) AS rank,
                   count(*) OVER () AS total
            FROM transcripts t, query
            WHERE tsv @@ query.tsq AND {where}
            ORDER BY rank DESC, posted_at DESC
            LIMIT %(limit)s OFFSET %(offset)s"""
    else:
        sql = f"""
            SELECT {META_COLS}, left(text, 320) AS snippet, NULL::float AS rank, count(*) OVER () AS total
            FROM transcripts t
            WHERE {where}
            ORDER BY posted_at DESC
            LIMIT %(limit)s OFFSET %(offset)s"""
    with pool.connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    total = rows[0]["total"] if rows else 0
    return total, rows
