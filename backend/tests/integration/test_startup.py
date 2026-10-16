"""App startup: schema, seeding an empty database, background warm-ups."""

from fastapi.testclient import TestClient

from app import main
from app.repositories import TranscriptRepository


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))


def run_lifespan(monkeypatch, empty: bool, seed_exists: bool):
    started, threads = Recorder(), Recorder()
    monkeypatch.setattr(TranscriptRepository, "prepare_database", staticmethod(lambda: empty))
    monkeypatch.setattr(main.settings, "seed_on_empty", True)
    monkeypatch.setattr(main.ingest_job, "start", started)
    monkeypatch.setattr(main.pool, "open", Recorder())
    monkeypatch.setattr(main.pool, "close", Recorder())
    monkeypatch.setattr(main.threading, "Thread", lambda **kw: type("T", (), {"start": lambda self: threads(kw)})())

    class News:
        refreshed = False

        def refresh_in_background(self):
            News.refreshed = True
    monkeypatch.setattr(main, "get_news", lambda: News())
    seed = type("Seed", (), {"exists": lambda self: seed_exists, "name": "seed.jsonl"})()
    monkeypatch.setattr(main, "SEED_FILE", seed)
    with TestClient(main.app) as c:
        assert c.get("/health").status_code == 200
    return started, threads, News.refreshed


def test_empty_database_is_seeded(monkeypatch):
    started, threads, refreshed = run_lifespan(monkeypatch, empty=True, seed_exists=True)
    assert len(started.calls) == 1 and started.calls[0][1]["label"] == "seed: seed.jsonl"
    assert not threads.calls and refreshed


def test_loaded_database_warms_the_embedder(monkeypatch):
    started, threads, refreshed = run_lifespan(monkeypatch, empty=False, seed_exists=True)
    assert not started.calls and len(threads.calls) == 1 and refreshed
