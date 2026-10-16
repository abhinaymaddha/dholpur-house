"""Base class for repositories: the only place in the app that talks SQL."""

from __future__ import annotations

from psycopg_pool import ConnectionPool

from app.database import pool as default_pool


class Repository:
    """Holds a connection pool and small query helpers. Pass a different pool in tests if needed."""

    def __init__(self, pool: ConnectionPool | None = None):
        self._pool = pool or default_pool

    def _all(self, sql: str, params: dict | tuple | None = None) -> list[dict]:
        with self._pool.connection() as conn:
            return conn.execute(sql, params).fetchall()

    def _one(self, sql: str, params: dict | tuple | None = None) -> dict | None:
        with self._pool.connection() as conn:
            return conn.execute(sql, params).fetchone()

    def _run(self, sql: str, params: dict | tuple | None = None) -> None:
        with self._pool.connection() as conn:
            conn.execute(sql, params)
            conn.commit()

    def ping(self) -> bool:
        return self._one("SELECT 1 AS ok")["ok"] == 1
