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
from app.ingest.tags import match_topics
from app.repositories import NewsRepository

logger = logging.getLogger(__name__)
DEFAULT_FILE = Path(__file__).resolve().parents[2] / "sources.toml"


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _published(entry) -> datetime:
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    return datetime(*t[:6], tzinfo=timezone.utc) if t else datetime.now(timezone.utc)


class NewsService:
    """Fetches the configured feeds, tags articles with topics and serves the recent ones."""

    def __init__(self, repo: NewsRepository, sources_file: Path | None = None):
        self.repo = repo
        self.sources_file = sources_file or (Path(settings.sources_file) if settings.sources_file else DEFAULT_FILE)
        self._lock = threading.Lock()

    def sources(self) -> dict:
        return tomllib.loads(self.sources_file.read_text(encoding="utf-8"))

    @staticmethod
    def topics_for(text: str, allowed: list[str] | None) -> list[str]:
        found = match_topics(text)
        return [t for t in found if t in allowed] if allowed else found

    @staticmethod
    def fetch(url: str):
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (dholpur-house)"}, timeout=15)
        r.raise_for_status()
        return feedparser.parse(r.content)

    def refresh(self, force: bool = False) -> dict:
        """Fetch feeds older than refresh_hours (all of them if force). Returns item counts per source."""
        cfg = self.sources()
        stale_after = timedelta(hours=cfg.get("refresh_hours", 6))
        now = datetime.now(timezone.utc)
        report: dict[str, int | str] = {}
        with self._lock:
            last = self.repo.fetch_times()
            for src in cfg.get("source", []):
                name = src["name"]
                if not force and name in last and now - last[name] < stale_after:
                    continue
                try:
                    feed = self.fetch(src["url"])
                except requests.RequestException as e:
                    logger.warning("feed %s failed: %s", name, e)
                    report[name] = f"error: {e}"
                    continue
                rows = []
                for e in feed.entries:
                    title, summary = _clean(e.get("title", "")), _clean(e.get("summary", ""))[:1200]
                    topics = self.topics_for(f"{title}. {summary}", src.get("topics"))
                    if e.get("link") and title and topics:
                        rows.append((e["link"], name, title, summary, _published(e), topics))
                self.repo.save_feed(name, rows, now)
                report[name] = len(rows)
            self.repo.prune(now - timedelta(days=cfg.get("keep_days", 21)))
        return report

    def refresh_in_background(self) -> threading.Thread:
        def run():
            try:
                self.refresh()
            except Exception:   # never let a feed problem take the app down
                logger.exception("news refresh failed")
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def recent(self, topics: list[str], limit: int = 6, exclude_urls: list[str] = ()) -> list[dict]:
        return self.repo.recent(topics, limit, exclude_urls)

    def topic_counts(self) -> dict[str, int]:
        return self.repo.topic_counts()
