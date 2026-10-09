"""Real past questions from the transcripts: drawn as interview questions and used as prompt examples."""

from __future__ import annotations

import re

from app.database import pool

DAF_TOPIC = "DAF & Background"
_COLS = "q.id, q.text, q.member, q.transcript_id, t.board, t.cse_year, t.alias"


def _topic_clause(topic: str) -> str:
    # DAF questions aren't a regex topic: approximate with personal/motivation questions and anything else
    return "'Motivation & Personal' = ANY(q.topics)" if topic == DAF_TOPIC else "%(topic)s = ANY(q.topics)"


def draw(topic: str, board: str | None, exclude_ids: list[int]) -> dict | None:
    """One real opening question (not a follow-up) on the topic, preferring the chosen board and recent years."""
    params = {"topic": topic, "board": board, "exclude": exclude_ids}
    for board_clause in (["t.board = %(board)s"] if board else []) + ["TRUE"]:
        row = None
        with pool.connection() as conn:
            row = conn.execute(f"""
                SELECT {_COLS} FROM questions q JOIN transcripts t ON t.id = q.transcript_id
                WHERE {_topic_clause(topic)} AND q.prev_id IS NULL AND {board_clause}
                  AND NOT (q.id = ANY(%(exclude)s::bigint[])) AND length(q.text) BETWEEN 25 AND 300
                ORDER BY random() * (CASE WHEN t.cse_year = (SELECT max(cse_year) FROM transcripts) THEN 1 ELSE 1.6 END)
                LIMIT 1""", params).fetchone()
        if row:
            return row
    return None


def examples(topic: str, board: str | None = None, n: int = 12, daf: str | None = None) -> list[dict]:
    """Real questions to show the model how boards ask about this topic (or about a DAF like this one)."""
    params = {"topic": topic, "n": n, "board": board}
    where = _topic_clause(topic)
    if topic == DAF_TOPIC and daf:
        words = [w for w in re.findall(r"[A-Za-z]{4,}", daf)][:12]
        if words:
            params["kq"] = " OR ".join(words)
            where = "q.tsv @@ websearch_to_tsquery('english', %(kq)s)"
    with pool.connection() as conn:
        return conn.execute(f"""
            SELECT {_COLS} FROM questions q JOIN transcripts t ON t.id = q.transcript_id
            WHERE {where} AND length(q.text) BETWEEN 25 AND 250
            ORDER BY (t.board = %(board)s) DESC NULLS LAST, random() LIMIT %(n)s""", params).fetchall()


def board_examples(board: str, n: int = 8) -> list[dict]:
    with pool.connection() as conn:
        return conn.execute(f"""
            SELECT {_COLS} FROM questions q JOIN transcripts t ON t.id = q.transcript_id
            WHERE t.board = %s AND length(q.text) BETWEEN 25 AND 250 ORDER BY random() LIMIT %s""", (board, n)).fetchall()


def followup_pairs(topic: str, n: int = 5) -> list[tuple[str, str]]:
    """(question, the same member's next question) pairs: how boards follow up on this topic."""
    with pool.connection() as conn:
        rows = conn.execute(f"""
            SELECT p.text AS q, q.text AS f FROM questions q JOIN questions p ON p.id = q.prev_id
            WHERE ({_topic_clause(topic).replace('q.topics', 'p.topics')})
              AND length(p.text) BETWEEN 20 AND 220 AND length(q.text) BETWEEN 15 AND 220
            ORDER BY random() LIMIT %(n)s""", {"topic": topic, "n": n}).fetchall()
    return [(r["q"], r["f"]) for r in rows]


def count_by_topic() -> dict[str, int]:
    with pool.connection() as conn:
        rows = conn.execute("SELECT unnest(topics) AS t, count(*) AS n FROM questions GROUP BY 1").fetchall()
    return {r["t"]: r["n"] for r in rows}


def fmt(rows: list[dict]) -> str:
    return "\n".join(f"- {r['text']}  _(CSE {r['cse_year']}, {r['board']} board)_" for r in rows) or "- (none found)"
