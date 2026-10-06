"""One background ingest at a time, with status for the admin API. Used by uploads and first-start seeding."""

from __future__ import annotations

import logging
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.ingest.pipeline import run_ingest

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_job: dict = {"state": "idle"}


class IngestRunning(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def status() -> dict:
    return dict(_job, log=list(_job.get("log", [])))


def start(source: Path, label: str, cleanup: Path | None = None) -> None:
    """Run run_ingest(source) in a thread. `cleanup` is a temp dir to delete afterwards."""
    with _lock:
        if _job.get("state") == "running":
            raise IngestRunning("an ingest is already running")
        _job.clear()
        _job.update(state="running", source=label, started_at=_now(), log=[])
    threading.Thread(target=_run, args=(source, cleanup), daemon=True).start()


def _run(source: Path, cleanup: Path | None) -> None:
    def log(line: str) -> None:
        logger.info("ingest: %s", line)
        _job["log"].append(line)

    try:
        _job.update(state="done", summary=run_ingest(source, log=log))
    except Exception as e:   # surface any failure through status()
        logger.exception("ingest failed")
        _job.update(state="failed", error=str(e))
    finally:
        _job["finished_at"] = _now()
        if cleanup:
            shutil.rmtree(cleanup, ignore_errors=True)
