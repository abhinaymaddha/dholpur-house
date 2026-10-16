"""Individual past questions: nearest by meaning, board samples, profile-matched candidates."""

from __future__ import annotations

from app.repositories.base import Repository

# A line a board member could read out as-is (used when real questions are asked directly), not narration
# such as "Some questions about books" or "Discussion on federalism".
ASKABLE = (r"q.text ~* '(\?\s*$|^\s*(what|why|how|who|whom|when|where|which|is|are|was|were|do|does|did|can|could|"
           r"should|would|will|have|has|tell|explain|describe|give|name|define|suggest|suppose|if|as a|as the|you|your)\M)'"
           r" AND q.text !~* '^\s*(some|few|many|asked|discussion|discussed|questions?|talked|long|then|also|rest|"
           r"any|and|so|but|does it|is it|was it|why so|how so|what about it)\M'"
           # stand-alone: at least five words, so it isn't a fragment that only makes sense after another question
           r" AND array_length(regexp_split_to_array(trim(q.text), '\s+'), 1) >= 5")

COLS = ("q.id, q.text, q.member, q.transcript_id, t.board, t.cse_year, t.alias, t.daf, "
        "(SELECT f.text FROM questions f WHERE f.prev_id = q.id LIMIT 1) AS follow_up")


class QuestionRepository(Repository):

    def nearest(self, vec, limit: int, *, board: str | None = None, exclude_ids: list[int] = (),
                exclude_transcript: str | None = None, askable: bool = False) -> list[dict]:
        """Questions closest in meaning to `vec` (with the follow-up asked next), closest first."""
        clauses = ["q.embedding IS NOT NULL", "length(q.text) BETWEEN 20 AND 300",
                   "NOT (q.id = ANY(%(exclude)s::bigint[]))"]
        if exclude_transcript:
            clauses.append("q.transcript_id <> %(tx)s")
        if board:
            clauses.append("t.board = %(board)s")
        if askable:
            clauses.append(ASKABLE)
        params = {"v": vec, "limit": limit, "exclude": list(exclude_ids), "tx": exclude_transcript, "board": board}
        with self._pool.connection() as conn:
            conn.execute("SET hnsw.ef_search = 100")
            return conn.execute(f"""
                SELECT {COLS}, q.embedding <=> %(v)s AS distance
                FROM questions q JOIN transcripts t ON t.id = q.transcript_id
                WHERE {' AND '.join(clauses)}
                ORDER BY q.embedding <=> %(v)s LIMIT %(limit)s""", params).fetchall()

    def board_sample(self, board: str, n: int = 8) -> list[dict]:
        return self._all(f"""
            SELECT {COLS} FROM questions q JOIN transcripts t ON t.id = q.transcript_id
            WHERE t.board = %s AND q.prev_id IS NULL AND length(q.text) BETWEEN 25 AND 250
            ORDER BY random() LIMIT %s""", (board, n))

    def topic_counts(self) -> dict[str, int]:
        rows = self._all("SELECT unnest(topics) AS t, count(*) AS n FROM questions GROUP BY 1")
        return {r["t"]: r["n"] for r in rows}

    def profile_matches(self, profile: dict, n: int = 2) -> list[dict]:
        """Transcripts whose candidate profile overlaps most with `profile` (state and optional weigh double)."""
        return self._all("""
            SELECT id, board, cse_year, alias, daf,
                   cardinality(ARRAY(SELECT unnest(background) INTERSECT SELECT unnest(%(bg)s::text[])))
                 + cardinality(ARRAY(SELECT unnest(states) INTERSECT SELECT unnest(%(st)s::text[]))) * 2
                 + cardinality(ARRAY(SELECT unnest(interests) INTERSECT SELECT unnest(%(it)s::text[])))
                 + (CASE WHEN optional_tag = %(op)s THEN 2 ELSE 0 END) AS score
            FROM transcripts WHERE question_count >= 12
            ORDER BY score DESC, random() LIMIT %(n)s""",
            {"bg": profile["background"], "st": profile["states"], "it": profile["interests"],
             "op": profile["optional_tag"], "n": n})

    def of_transcript(self, transcript_id: str, n: int = 24) -> list[dict]:
        return self._all("SELECT member, text FROM questions WHERE transcript_id = %s ORDER BY id LIMIT %s",
                         (transcript_id, n))
