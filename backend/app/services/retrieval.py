"""Hybrid retrieval for RAG: pgvector similarity + full-text match over chunks, fused by rank.

Chunks are member sections of a transcript (Chairman / M1 / ...). We rank chunks both ways,
combine with reciprocal rank fusion, then group by transcript so the LLM sees whole candidates
with their most relevant sections.
"""

from __future__ import annotations

import re
from collections import defaultdict

from app.database import pool
from app.services.embeddings import embed_one
from app.services.search import filter_sql

CANDIDATES = 40       # chunks pulled from each ranker
RRF_K = 60
STOPWORDS = {"what", "which", "when", "where", "who", "whom", "why", "how", "the", "and", "for", "are", "was",
             "were", "did", "does", "about", "asked", "ask", "questions", "question", "board", "boards", "they",
             "with", "from", "that", "this", "candidates", "candidate", "interview", "interviews", "upsc"}


def _keyword_query(question: str) -> str:
    """Natural-language questions rarely match with AND semantics; OR the content words instead."""
    words = [w for w in re.findall(r"\w+", question.lower()) if len(w) > 2 and w not in STOPWORDS]
    return " OR ".join(words)


def _transcript_score(chunk_scores: list[float]) -> float:
    """Best chunk, plus a little credit for further matching chunks in the same transcript."""
    best = max(chunk_scores)
    return best + 0.25 * (sum(chunk_scores) - best)


def retrieve(question: str, board: str | None, cse_year: int | None, exam: str | None,
             top_k: int = 6, chunks_per_transcript: int = 3) -> list[dict]:
    where, params = filter_sql(board, cse_year, exam)
    params |= {"vec": embed_one(question), "kq": _keyword_query(question), "n": CANDIDATES}
    with pool.connection() as conn:
        conn.execute("SET hnsw.ef_search = 200")   # filters are applied after the ANN scan; widen it
        vec_rows = conn.execute(f"""
            SELECT c.id, c.transcript_id, c.seq, c.section, c.text
            FROM chunks c JOIN transcripts t ON t.id = c.transcript_id
            WHERE {where}
            ORDER BY c.embedding <=> %(vec)s
            LIMIT %(n)s""", params).fetchall()
        kw_rows = []
        if params["kq"]:
            kw_rows = conn.execute(f"""
                WITH query AS (SELECT websearch_to_tsquery('english', %(kq)s) AS tsq)
                SELECT c.id, c.transcript_id, c.seq, c.section, c.text
                FROM chunks c JOIN transcripts t ON t.id = c.transcript_id, query
                WHERE c.tsv @@ query.tsq AND {where}
                ORDER BY ts_rank_cd(c.tsv, query.tsq) DESC
                LIMIT %(n)s""", params).fetchall()

        chunk_by_id, score = {}, defaultdict(float)
        for rows in (vec_rows, kw_rows):
            for rank, r in enumerate(rows):
                chunk_by_id[r["id"]] = r
                score[r["id"]] += 1 / (RRF_K + rank + 1)

        per_transcript: dict[str, list[tuple[float, dict]]] = defaultdict(list)
        for cid, s in score.items():
            per_transcript[chunk_by_id[cid]["transcript_id"]].append((s, chunk_by_id[cid]))
        ranked = sorted(per_transcript.items(), key=lambda kv: -_transcript_score([s for s, _ in kv[1]]))
        top = ranked[:top_k]
        if not top:
            return []
        meta = {r["id"]: r for r in conn.execute(
            "SELECT id, board, alias, interview_date, daf, optional_subject, pt_marks, exam, cse_year, posted_at,"
            " telegram_url FROM transcripts WHERE id = ANY(%s)", ([tid for tid, _ in top],)).fetchall()}

    results = []
    for tid, scored in top:
        best = sorted(scored, key=lambda x: -x[0])[:chunks_per_transcript]
        results.append({
            **meta[tid],
            "score": round(max(s for s, _ in scored), 5),
            "excerpts": [{"section": c["section"], "text": c["text"]} for _, c in sorted(best, key=lambda x: x[1]["seq"])],
        })
    return results
