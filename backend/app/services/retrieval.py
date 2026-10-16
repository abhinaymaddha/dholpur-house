"""Hybrid retrieval for RAG: pgvector similarity + full-text match over chunks, fused by rank.

Chunks are member sections of a transcript (Chairman / M1 / ...). We rank chunks both ways,
combine with reciprocal rank fusion, then group by transcript so the LLM sees whole candidates
with their most relevant sections.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable

from app.repositories import ChunkRepository, TranscriptRepository
from app.schemas.filters import TranscriptFilters
from app.services.embeddings import embed_one

STOPWORDS = {"what", "which", "when", "where", "who", "whom", "why", "how", "the", "and", "for", "are", "was",
             "were", "did", "does", "about", "asked", "ask", "questions", "question", "board", "boards", "they",
             "with", "from", "that", "this", "candidates", "candidate", "interview", "interviews", "upsc"}


class HybridRetriever:
    candidates = 40      # chunks pulled from each ranker
    rrf_k = 60

    def __init__(self, chunks: ChunkRepository, transcripts: TranscriptRepository,
                 embed: Callable[[str], object] = embed_one):
        self.chunks = chunks
        self.transcripts = transcripts
        self.embed = embed

    @staticmethod
    def keyword_query(question: str) -> str:
        """Natural-language questions rarely match with AND semantics; OR the content words instead."""
        words = [w for w in re.findall(r"\w+", question.lower()) if len(w) > 2 and w not in STOPWORDS]
        return " OR ".join(words)

    @staticmethod
    def transcript_score(chunk_scores: list[float]) -> float:
        """Best chunk, plus a little credit for further matching chunks in the same transcript."""
        best = max(chunk_scores)
        return best + 0.25 * (sum(chunk_scores) - best)

    def fuse(self, *rankings: list[dict]) -> dict[str, list[tuple[float, dict]]]:
        """Reciprocal rank fusion of chunk rankings, grouped by transcript."""
        chunk_by_id, score = {}, defaultdict(float)
        for rows in rankings:
            for rank, r in enumerate(rows):
                chunk_by_id[r["id"]] = r
                score[r["id"]] += 1 / (self.rrf_k + rank + 1)
        grouped: dict[str, list[tuple[float, dict]]] = defaultdict(list)
        for cid, s in score.items():
            grouped[chunk_by_id[cid]["transcript_id"]].append((s, chunk_by_id[cid]))
        return grouped

    def retrieve(self, question: str, filters: TranscriptFilters, top_k: int = 6, chunks_per_transcript: int = 3,
                 q: str = "", exclude: tuple[str, ...] = ()) -> list[dict]:
        """Top transcripts for a question, within the filters (and keyword matches for q), best sections first."""
        by_vector = self.chunks.nearest(self.embed(question), filters, self.candidates, q, exclude)
        by_keyword = self.chunks.keyword(self.keyword_query(question), filters, self.candidates, q, exclude)
        grouped = self.fuse(by_vector, by_keyword)
        top = sorted(grouped.items(), key=lambda kv: -self.transcript_score([s for s, _ in kv[1]]))[:top_k]
        if not top:
            return []
        meta = self.transcripts.meta([tid for tid, _ in top])
        results = []
        for tid, scored in top:
            best = sorted(scored, key=lambda x: -x[0])[:chunks_per_transcript]
            results.append({
                **meta[tid],
                "score": round(max(s for s, _ in scored), 5),
                "excerpts": [{"section": c["section"], "text": c["text"]}
                             for _, c in sorted(best, key=lambda x: x[1]["seq"])],
            })
        return results
