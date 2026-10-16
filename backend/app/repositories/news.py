"""Current-affairs articles and when each feed was last fetched."""

from __future__ import annotations

from datetime import datetime

from app.repositories.base import Repository


class NewsRepository(Repository):

    def fetch_times(self) -> dict[str, datetime]:
        return {r["source"]: r["fetched_at"] for r in self._all("SELECT source, fetched_at FROM news_fetches")}

    def save_feed(self, source: str, items: list[tuple], fetched_at: datetime) -> None:
        """Upsert a feed's items (url, source, title, summary, published_at, topics) and record the fetch."""
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO news_items (url, source, title, summary, published_at, topics) VALUES (%s, %s, %s, %s, %s, %s)"
                    " ON CONFLICT (url) DO UPDATE SET title = EXCLUDED.title, summary = EXCLUDED.summary,"
                    " topics = EXCLUDED.topics", items)
                cur.execute("INSERT INTO news_fetches (source, fetched_at) VALUES (%s, %s)"
                            " ON CONFLICT (source) DO UPDATE SET fetched_at = EXCLUDED.fetched_at", (source, fetched_at))
            conn.commit()

    def prune(self, older_than: datetime) -> None:
        self._run("DELETE FROM news_items WHERE published_at < %s", (older_than,))

    def recent(self, topics: list[str], limit: int = 6, exclude_urls: list[str] = ()) -> list[dict]:
        """Newest articles for any of the topics, skipping ones already used."""
        return self._all(
            "SELECT url, source, title, summary, published_at, topics FROM news_items"
            " WHERE topics && %s::text[] AND NOT (url = ANY(%s::text[]))"
            " ORDER BY published_at DESC LIMIT %s", (topics, list(exclude_urls), limit))

    def topic_counts(self) -> dict[str, int]:
        rows = self._all("SELECT unnest(topics) AS t, count(*) AS n FROM news_items GROUP BY 1")
        return {r["t"]: r["n"] for r in rows}
