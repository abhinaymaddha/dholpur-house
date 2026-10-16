"""Interview conversations: sessions and their turns (a question and, once answered, its evaluation)."""

from __future__ import annotations

from uuid import UUID

from psycopg.types.json import Jsonb

from app.repositories.base import Repository

_TURN = "id, main_index, depth, topic, question, source, answer, evaluation, mode"


class InterviewRepository(Repository):

    def session_exists(self, session_id: UUID) -> bool:
        return self._one("SELECT 1 AS ok FROM interview_sessions WHERE id = %s", (session_id,)) is not None

    def create_session(self) -> UUID:
        with self._pool.connection() as conn:
            sid = conn.execute("INSERT INTO interview_sessions DEFAULT VALUES RETURNING id").fetchone()["id"]
            conn.commit()
        return sid

    def turns(self, session_id: UUID) -> list[dict]:
        return self._all(f"SELECT {_TURN} FROM interview_turns WHERE session_id = %s ORDER BY id", (session_id,))

    def turn(self, turn_id: int) -> dict | None:
        return self._one(f"SELECT {_TURN} FROM interview_turns WHERE id = %s", (turn_id,))

    def add_turn(self, session_id: UUID, main_index: int, depth: int, topic: str, question: str, source: dict) -> dict:
        with self._pool.connection() as conn:
            row = conn.execute(
                "INSERT INTO interview_turns (session_id, main_index, depth, topic, question, source)"
                f" VALUES (%s, %s, %s, %s, %s, %s) RETURNING {_TURN}",
                (session_id, main_index, depth, topic, question, Jsonb(source))).fetchone()
            conn.commit()
        return row

    def save_answer(self, turn_id: int, answer: str, evaluation: dict, mode: str) -> None:
        self._run("UPDATE interview_turns SET answer = %s, evaluation = %s, mode = %s WHERE id = %s",
                  (answer, Jsonb(evaluation), mode, turn_id))

    def mark_skipped(self, turn_id: int) -> None:
        self._run("UPDATE interview_turns SET evaluation = %s WHERE id = %s", (Jsonb({"skipped": True}), turn_id))
