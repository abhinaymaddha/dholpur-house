"""Shared test setup.

Tests run against a real Postgres + pgvector database (TEST_DATABASE_URL, default upsc_test on
localhost), loaded once per run by the real ingest pipeline from a synthetic Telegram export.
Embeddings are a deterministic stand-in and every LLM call goes to FakeProvider, so no model
downloads, no network and no API keys are needed.
"""

import os
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

# Before anything imports app.config: point the app at the test database and test configs.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "postgresql://upsc:upsc@localhost:5432/upsc_test")
os.environ["MODELS_FILE"] = str(FIXTURES / "models.toml")
os.environ["SOURCES_FILE"] = str(FIXTURES / "sources.toml")
os.environ["SEED_ON_EMPTY"] = "false"
os.environ["ADMIN_TOKEN"] = ""

import psycopg   # noqa: E402
import pytest   # noqa: E402
from fastapi.testclient import TestClient   # noqa: E402

from app.config import settings   # noqa: E402
from app.services import embeddings   # noqa: E402
from tests.fixtures.export import write_export   # noqa: E402
from tests.fixtures.fakes import FakeEmbedder, FakeProvider   # noqa: E402


REAL_EMBED_MODEL = embeddings._model   # kept for the test of the model loader itself


@pytest.fixture(scope="session", autouse=True)
def database(tmp_path_factory):
    """Ingest the synthetic export into the test database once, and open the app's pool."""
    from app.database import pool
    from app.ingest.pipeline import run_ingest

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(embeddings, "_model", lambda: FakeEmbedder())
        with psycopg.connect(settings.database_url, autocommit=True) as conn:
            conn.execute("DROP TABLE IF EXISTS interview_turns, interview_sessions, news_items, news_fetches, "
                         "questions, chunks, transcripts, held CASCADE")
        summary = run_ingest(write_export(tmp_path_factory.mktemp("export")), log=lambda _: None)
        pool.open(wait=True)
        yield summary
        pool.close()


@pytest.fixture(autouse=True)
def fake_llm():
    FakeProvider.reset()
    yield FakeProvider
    FakeProvider.reset()


@pytest.fixture
def sql():
    """Run a statement against the test database (for test setup and assertions only)."""
    def run(query: str, params=None):
        with psycopg.connect(settings.database_url, autocommit=True, row_factory=psycopg.rows.dict_row) as conn:
            cur = conn.execute(query, params)
            return cur.fetchall() if cur.description else None
    return run


@pytest.fixture
def client():
    """The real app without its startup hooks (the session fixture already prepared the database)."""
    from app.main import app
    app.dependency_overrides.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()
