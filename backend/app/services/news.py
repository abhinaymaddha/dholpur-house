"""Current-affairs articles from the feeds in sources.toml, tagged with interview topics."""

from __future__ import annotations

import html
import logging
import re
import threading
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests

from app.config import settings
from app.database import pool
from app.ingest.tags import match_topics

logger = logging.getLogger(__name__)
DEFAULT_FILE = Path(__file__).resolve().parents[2] / "sources.toml"
_refresh_lock = threading.Lock()


def load_sources() -> dict:
    path = Path(settings.sources_file) if settings.sources_file else DEFAULT_FILE
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _published(entry) -> datetime:
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    return datetime(*t[:6], tzinfo=timezone.utc) if t else datetime.now(timezone.utc)


def _topics(text: str, allowed: list[str] | None) -> list[str]:
    found = match_topics(text)
    return [t for t in found if t in allowed] if allowed else found


def refresh(force: bool = False) -> dict:
    """Fetch feeds that are older than refresh_hours (all of them if force). Returns counts per source."""
    cfg = load_sources()
    stale_after = timedelta(hours=cfg.get("refresh_hours", 6))
    now = datetime.now(timezone.utc)
    report = {}
    with _refresh_lock, pool.connection() as conn:
        last = {r["source"]: r["fetched_at"] for r in conn.execute("SELECT source, fetched_at FROM news_fetches")}
        for src in cfg.get("source", []):
            name = src["name"]
            if not force and name in last and now - last[name] < stale_after:
                continue
            try:
                r = requests.get(src["url"], headers={"User-Agent": "Mozilla/5.0 (upsc-prep)"}, timeout=15)
                r.raise_for_status()
                feed = feedparser.parse(r.content)
            except requests.RequestException as e:
                logger.warning("feed %s failed: %s", name, e)
                report[name] = f"error: {e}"
                continue
            rows = []
            for e in feed.entries:
                title, summary = _clean(e.get("title", "")), _clean(e.get("summary", ""))[:1200]
                topics = _topics(f"{title}. {summary}", src.get("topics"))
                if e.get("link") and title and topics:
                    rows.append((e["link"], name, title, summary, _published(e), topics))
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO news_items (url, source, title, summary, published_at, topics) VALUES (%s, %s, %s, %s, %s, %s)"
                    " ON CONFLICT (url) DO UPDATE SET title = EXCLUDED.title, summary = EXCLUDED.summary,"
                    " topics = EXCLUDED.topics", rows)
                cur.execute("INSERT INTO news_fetches (source, fetched_at) VALUES (%s, %s)"
                            " ON CONFLICT (source) DO UPDATE SET fetched_at = EXCLUDED.fetched_at", (name, now))
            report[name] = len(rows)
        conn.execute("DELETE FROM news_items WHERE published_at < %s", (now - timedelta(days=cfg.get("keep_days", 21)),))
        conn.commit()
    return report


def refresh_in_background() -> None:
    def run():
        try:
            refresh()
        except Exception:   # never let a feed problem take the app down
            logger.exception("news refresh failed")
    threading.Thread(target=run, daemon=True).start()


def recent(topics: list[str], limit: int = 6, exclude_urls: list[str] = ()) -> list[dict]:
    """Newest articles for any of the topics, skipping ones already used in this conversation."""
    with pool.connection() as conn:
        return conn.execute(
            "SELECT url, source, title, summary, published_at, topics FROM news_items"
            " WHERE topics && %s::text[] AND NOT (url = ANY(%s::text[]))"
            " ORDER BY published_at DESC LIMIT %s", (topics, list(exclude_urls), limit)).fetchall()
