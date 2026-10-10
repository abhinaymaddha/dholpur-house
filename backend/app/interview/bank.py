"""Real past questions from the transcripts, searched by meaning (question embeddings).

Used three ways: as examples that ground generated questions, as questions asked directly in
"real questions only" mode, and as question → follow-up pairs that show how boards follow up.
"""

from __future__ import annotations

import numpy as np

from app.database import pool
from app.ingest.tags import profile_tags
from app.services.embeddings import embed

_COLS = ("q.id, q.text, q.member, q.transcript_id, t.board, t.cse_year, t.alias, t.daf, "
         "(SELECT f.text FROM questions f WHERE f.prev_id = q.id LIMIT 1) AS follow_up")


def similar(queries: list[str], n: int = 12, board: str | None = None, exclude_ids: list[int] = (),
            exclude_transcript: str | None = None, prefer_board: bool = True) -> list[dict]:
    """Past questions closest in meaning to any of the query texts, best first, de-duplicated.

    With a board, half the results come from that board (if it has enough) so its style shows through.
    """
    if not queries:
        return []
    vectors: list[np.ndarray] = embed(queries)
    per_query = max(4, n // len(queries) + 2)
    found: dict[int, dict] = {}

    def run(vec, limit, board_only):
        clauses = ["q.embedding IS NOT NULL", "length(q.text) BETWEEN 20 AND 300",
                   "NOT (q.id = ANY(%(exclude)s::bigint[]))"]
        if exclude_transcript:
            clauses.append("q.transcript_id <> %(tx)s")
        if board_only:
            clauses.append("t.board = %(board)s")
        params = {"v": vec, "limit": limit, "exclude": list(exclude_ids), "tx": exclude_transcript, "board": board}
        with pool.connection() as conn:
            conn.execute("SET hnsw.ef_search = 100")
            return conn.execute(f"""
                SELECT {_COLS}, q.embedding <=> %(v)s AS distance
                FROM questions q JOIN transcripts t ON t.id = q.transcript_id
                WHERE {' AND '.join(clauses)}
                ORDER BY q.embedding <=> %(v)s LIMIT %(limit)s""", params).fetchall()

    for vec in vectors:
        rows = (run(vec, per_query // 2 + 1, True) if board and prefer_board else []) + run(vec, per_query, False)
        for r in rows:
            if r["id"] not in found or r["distance"] < found[r["id"]]["distance"]:
                found[r["id"]] = r
    # also drop near-identical wording (the same question reposted or asked twice)
    out, seen = [], set()
    for r in sorted(found.values(), key=lambda r: r["distance"]):
        key = r["text"].lower()[:60]
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out[:n]


def similar_candidates(daf: str, n: int = 2) -> list[dict]:
    """Transcripts of candidates whose profile best matches this DAF, with their questions in order."""
    p = profile_tags(daf)
    if not any(p.values()):
        return []
    with pool.connection() as conn:
        picks = conn.execute("""
            SELECT id, board, cse_year, alias, daf,
                   cardinality(ARRAY(SELECT unnest(background) INTERSECT SELECT unnest(%(bg)s::text[])))
                 + cardinality(ARRAY(SELECT unnest(states) INTERSECT SELECT unnest(%(st)s::text[]))) * 2
                 + cardinality(ARRAY(SELECT unnest(interests) INTERSECT SELECT unnest(%(it)s::text[])))
                 + (CASE WHEN optional_tag = %(op)s THEN 2 ELSE 0 END) AS score
            FROM transcripts WHERE question_count >= 12
            ORDER BY score DESC, random() LIMIT %(n)s""",
            {"bg": p["background"], "st": p["states"], "it": p["interests"], "op": p["optional_tag"], "n": n}).fetchall()
        result = []
        for t in picks:
            if not t["score"]:
                continue
            qs = conn.execute("SELECT member, text FROM questions WHERE transcript_id = %s ORDER BY id LIMIT 24",
                              (t["id"],)).fetchall()
            result.append({**t, "questions": qs})
    return result


def board_examples(board: str, n: int = 8) -> list[dict]:
    with pool.connection() as conn:
        return conn.execute(f"""
            SELECT {_COLS} FROM questions q JOIN transcripts t ON t.id = q.transcript_id
            WHERE t.board = %s AND q.prev_id IS NULL AND length(q.text) BETWEEN 25 AND 250
            ORDER BY random() LIMIT %s""", (board, n)).fetchall()


def count_by_topic() -> dict[str, int]:
    with pool.connection() as conn:
        rows = conn.execute("SELECT unnest(topics) AS t, count(*) AS n FROM questions GROUP BY 1").fetchall()
    return {r["t"]: r["n"] for r in rows}


def fmt(rows: list[dict], with_follow_up: bool = True) -> str:
    lines = []
    for r in rows:
        lines.append(f"- {r['text']}  _(CSE {r['cse_year']}, {r['board']} board)_")
        if with_follow_up and r.get("follow_up"):
            lines.append(f"  - then: {r['follow_up']}")
    return "\n".join(lines) or "- (none found)"


def fmt_candidates(cands: list[dict]) -> str:
    blocks = []
    for c in cands:
        qs = "\n".join(f"  {q['member']}: {q['text']}" for q in c["questions"])
        blocks.append(f"### Candidate with DAF: {c['daf'] or 'n/a'} ({c['board']} board, CSE {c['cse_year']})\n{qs}")
    return "\n\n".join(blocks) or "(no close profile match)"
