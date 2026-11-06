"""Limits on the AI-backed endpoints, so one visitor (or a script) can't use up the day's model quota.

Per visitor: requests per minute and per day across Ask AI and Interview. Site-wide: a daily budget for
calls that reach the LLM, kept below the provider's free-tier limit. Counters live in memory: the API runs
as one process, and a restart simply starts the counts afresh.
"""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Callable

from app.errors import RateLimited


class RateLimiter:

    def __init__(self, per_minute: int, per_day: int, daily_budget: int,
                 clock: Callable[[], float] = time.time):
        self.per_minute = per_minute
        self.per_day = per_day
        self.daily_budget = daily_budget
        self.clock = clock
        self._lock = Lock()
        self._recent: dict[str, deque[float]] = {}
        self._day = ""
        self._daily: dict[str, int] = {}
        self._ai_today = 0

    def _roll_day(self, now: float) -> None:
        day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()   # providers reset at UTC midnight
        if day != self._day:
            self._day, self._daily, self._ai_today = day, {}, 0

    def check(self, visitor: str, uses_ai: bool = True, ai_calls: int = 1) -> None:
        """Count one request and the model calls it leads to, or raise RateLimited (and count nothing) if it would
        exceed a limit."""
        with self._lock:
            now = self.clock()
            self._roll_day(now)
            recent = self._recent.setdefault(visitor, deque())
            while recent and recent[0] <= now - 60:
                recent.popleft()
            if len(recent) >= self.per_minute:
                raise RateLimited("You're going a bit fast. Please wait a minute and try again.")
            if self._daily.get(visitor, 0) >= self.per_day:
                raise RateLimited("You've reached today's limit for AI features. Please come back tomorrow.")
            if uses_ai and self._ai_today + ai_calls > self.daily_budget:
                raise RateLimited("The site has reached today's limit for AI features. Please come back tomorrow; "
                                  "browsing and real past questions still work.")
            recent.append(now)
            self._daily[visitor] = self._daily.get(visitor, 0) + 1
            self._ai_today += ai_calls if uses_ai else 0
            if len(self._recent) > 10_000:   # forget idle visitors so memory stays bounded
                self._recent = {k: v for k, v in self._recent.items() if v and v[-1] > now - 60}
