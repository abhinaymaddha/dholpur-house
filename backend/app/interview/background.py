"""Work the candidate shouldn't have to wait for: the next question and the full critique of an answer.

Kept in memory, because the API runs as one process. A restart loses nothing that matters: a prepared
question is simply written again when asked for, and the report restarts any evaluation left unfinished.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from threading import Lock
from typing import Callable
from uuid import UUID

logger = logging.getLogger(__name__)


class BackgroundWork:

    def __init__(self, executor: Executor | None = None, workers: int = 4, keep: int = 1000):
        self._executor = executor or ThreadPoolExecutor(max_workers=workers, thread_name_prefix="interview")
        self._keep = keep       # abandoned interviews' prepared questions are dropped, oldest first
        self._lock = Lock()
        self._prepared: OrderedDict[UUID, tuple[tuple, Future]] = OrderedDict()
        self._running: set[int] = set()

    def prepare(self, session_id: UUID, key: tuple, write: Callable[[], object]) -> None:
        """Start writing a session's next question, unless the same one is already prepared."""
        with self._lock:
            current = self._prepared.get(session_id)
            if current and current[0] == key:
                return
            self._prepared[session_id] = (key, self._executor.submit(write))
            self._prepared.move_to_end(session_id)
            while len(self._prepared) > self._keep:
                self._prepared.popitem(last=False)

    def take(self, session_id: UUID, key: tuple) -> object | None:
        """The prepared question for this key, waiting if it is still being written. None means write it now:
        nothing was prepared, the candidate changed their choices since, or the writing failed."""
        with self._lock:
            entry = self._prepared.pop(session_id, None)
        if not entry or entry[0] != key:
            return None
        try:
            return entry[1].result()
        except Exception as e:
            logger.warning("Preparing a question failed: %s", e)
            return None

    def evaluate(self, turn_id: int, task: Callable[[], None]) -> None:
        """Run a turn's evaluation, unless it is already running."""
        with self._lock:
            if turn_id in self._running:
                return
            self._running.add(turn_id)

        def run() -> None:
            try:
                task()
            except Exception:
                logger.exception("Evaluating turn %s failed", turn_id)
            finally:
                with self._lock:
                    self._running.discard(turn_id)

        self._executor.submit(run)
