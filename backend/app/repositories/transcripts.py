"""Transcripts: keyword search, filtered listing, facet counts, single reads, and the full reload at ingest."""

from __future__ import annotations

from psycopg import connect

from app.config import settings
from app.database import init_schema
from app.repositories.base import Repository
from app.repositories.filters import filter_sql
from app.schemas.filters import TranscriptFilters

# Highlight markers that won't occur in transcript text; the UI escapes the snippet and swaps these
# for <mark> tags, so transcript content is never rendered as HTML.
HL_START, HL_END = "⟦", "⟧"
HEADLINE_OPTS = (f"StartSel={HL_START}, StopSel={HL_END}, MaxFragments=3, MaxWords=28, MinWords=10, "
                 "FragmentDelimiter=\" … \"")
META_COLS = ("id, board, alias, interview_date, daf, optional_subject, pt_marks, exam, cse_year, posted_at, "
             "telegram_url, background, optional_tag, states, interests, topics, question_count")
SORTS = {"recent": "posted_at DESC", "questions": "question_count DESC, posted_at DESC",
         "marks": "pt_marks DESC NULLS LAST, posted_at DESC"}


class TranscriptRepository(Repository):

    def search(self, q: str, f: TranscriptFilters, limit: int, offset: int,
               sort: str = "relevance") -> tuple[int, list[dict]]:
        """Filtered listing; with keywords, matching transcripts with highlighted snippets.

        sort: relevance (keyword rank; newest first without keywords), recent, questions, marks.
        """
        where, params = filter_sql(f)
        params |= {"q": q.strip(), "limit": limit, "offset": offset, "opts": HEADLINE_OPTS}
        order = SORTS.get(sort, "posted_at DESC")
        if params["q"]:
            if sort == "relevance":
                order = "rank DESC, posted_at DESC"
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
        rows = self._all(sql, params)
        return (rows[0]["total"] if rows else 0), rows

    def facets(self, f: TranscriptFilters, q: str = "") -> dict:
        """Counts for every filter group, within the keyword matches if q is given.

        Each group ignores its own selection, so siblings stay visible.
        """
        with self._pool.connection() as conn:
            def counts(expr: str, skip: tuple[str, ...], array: bool = False) -> list[dict]:
                where, params = filter_sql(f, skip, q)
                value = f"unnest({expr})" if array else expr
                return conn.execute(
                    f"SELECT v::text AS value, count(*) AS count FROM (SELECT {value} AS v FROM transcripts t "
                    f"WHERE {where}) x WHERE v IS NOT NULL GROUP BY v ORDER BY count DESC, value", params).fetchall()

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
                "exam": counts("t.exam", ("exam",)),
                "background": counts("t.background", ("background",), array=True),
                "optional_tag": counts("t.optional_tag", ("optional_tag",)),
                "state": counts("t.states", ("state",), array=True),
                "interest": counts("t.interests", ("interest",), array=True),
                "topic": counts("t.topics", (), array=True),   # topics combine with AND: narrow within selection
                "has_marks": with_marks,
            }
        tree: dict[int, dict] = {}
        for r in tree_rows:
            year = tree.setdefault(r["cse_year"], {"year": r["cse_year"], "count": 0, "boards": []})
            year["count"] += r["count"]
            year["boards"].append({"value": r["board"], "count": r["count"]})
        result["tree"] = list(tree.values())
        return result

    def get(self, transcript_id: str) -> dict | None:
        return self._one("SELECT * FROM transcripts WHERE id = %s", (transcript_id,))

    def meta(self, ids: list[str]) -> dict[str, dict]:
        rows = self._all(f"SELECT {META_COLS} FROM transcripts WHERE id = ANY(%s)", (ids,))
        return {r["id"]: r for r in rows}

    def is_empty(self) -> bool:
        return self._one("SELECT NOT EXISTS (SELECT 1 FROM transcripts) AS empty")["empty"]

    def stats(self) -> dict:
        counts = self._one("SELECT (SELECT count(*) FROM transcripts) AS transcripts, (SELECT count(*) FROM held) AS held,"
                           " (SELECT count(*) FROM chunks) AS chunks")

        def facet(col: str) -> list[dict]:
            return self._all(f"SELECT {col}::text AS value, count(*) AS count FROM transcripts GROUP BY {col} "
                             "ORDER BY count DESC")

        return {**counts, "boards": facet("board"), "years": facet("cse_year"), "exams": facet("exam")}

    @staticmethod
    def prepare_database() -> bool:
        """Apply the schema before the pool opens (pooled connections register the vector type, so the
        extension must exist first). Returns True when there are no transcripts yet."""
        with connect(settings.database_url, autocommit=True) as conn:
            init_schema(conn)
            return conn.execute("SELECT NOT EXISTS (SELECT 1 FROM transcripts)").fetchone()[0]

    @staticmethod
    def replace_all(transcripts: list[dict], held: list[tuple], chunks: list[tuple], questions: list[dict]) -> None:
        """Replace every transcript, held unit, chunk and question in one transaction (used by ingest).

        Uses its own connection, so it also works from the CLI where the app's pool isn't open.
        """
        with connect(settings.database_url, autocommit=False) as conn:
            init_schema(conn)
            conn.execute("TRUNCATE questions, chunks, transcripts, held RESTART IDENTITY")
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO transcripts (id, message_ids, posted_at, telegram_url, board, alias, interview_date, daf,"
                    " optional_subject, pt_marks, exam, cse_year, reactions, duplicates, text, background, optional_tag,"
                    " states, interests, topics, question_count, structure) VALUES"
                    " (%(id)s, %(message_ids)s, %(posted_at)s, %(telegram_url)s, %(board)s, %(alias)s, %(interview_date)s,"
                    " %(daf)s, %(optional_subject)s, %(pt_marks)s, %(exam)s, %(cse_year)s, %(reactions)s, %(duplicates)s,"
                    " %(text)s, %(background)s, %(optional_tag)s, %(states)s, %(interests)s, %(topics)s,"
                    " %(question_count)s, %(structure)s)", transcripts)
                cur.executemany(
                    "INSERT INTO held (id, reason, message_ids, posted_at, text) VALUES (%s, %s, %s, %s, %s)", held)
                cur.executemany(
                    "INSERT INTO chunks (transcript_id, seq, section, text, embedding) VALUES (%s, %s, %s, %s, %s)", chunks)
                cur.executemany(
                    "INSERT INTO questions (id, transcript_id, seq, member, text, topics, prev_id, embedding) VALUES"
                    " (%(id)s, %(transcript_id)s, %(seq)s, %(member)s, %(text)s, %(topics)s, %(prev_id)s, %(embedding)s)",
                    questions)
                cur.execute("SELECT setval('questions_id_seq', GREATEST((SELECT max(id) FROM questions), 1))")
            conn.commit()
