"""Transcript sections (chunks) for RAG retrieval: vector and keyword candidates."""

from __future__ import annotations

from app.repositories.base import Repository
from app.repositories.filters import filter_sql
from app.schemas.filters import TranscriptFilters

_COLS = "c.id, c.transcript_id, c.seq, c.section, c.text"


class ChunkRepository(Repository):

    @staticmethod
    def _where(filters: TranscriptFilters, q: str, exclude: tuple[str, ...]) -> tuple[str, dict]:
        where, params = filter_sql(filters, q=q)
        if exclude:
            where += " AND NOT (t.id = ANY(%(exclude)s))"
            params["exclude"] = list(exclude)
        return where, params

    def nearest(self, vec, filters: TranscriptFilters, limit: int, q: str = "",
                exclude: tuple[str, ...] = ()) -> list[dict]:
        where, params = self._where(filters, q, exclude)
        with self._pool.connection() as conn:
            conn.execute("SET hnsw.ef_search = 200")   # filters are applied after the ANN scan; widen it
            return conn.execute(f"""
                SELECT {_COLS} FROM chunks c JOIN transcripts t ON t.id = c.transcript_id
                WHERE {where} ORDER BY c.embedding <=> %(vec)s LIMIT %(n)s""",
                params | {"vec": vec, "n": limit}).fetchall()

    def keyword(self, terms: str, filters: TranscriptFilters, limit: int, q: str = "",
                exclude: tuple[str, ...] = ()) -> list[dict]:
        """Chunks matching any of the terms (an OR query), best match first."""
        if not terms:
            return []
        where, params = self._where(filters, q, exclude)
        return self._all(f"""
            WITH query AS (SELECT websearch_to_tsquery('english', %(kq)s) AS tsq)
            SELECT {_COLS} FROM chunks c JOIN transcripts t ON t.id = c.transcript_id, query
            WHERE c.tsv @@ query.tsq AND {where}
            ORDER BY ts_rank_cd(c.tsv, query.tsq) DESC LIMIT %(n)s""", params | {"kq": terms, "n": limit})
