"""Follow-up rules of Interview mode, against a real database with the LLM stubbed out.

Needs DATABASE_URL pointing at an ingested database; skipped otherwise.
"""
import pytest
from psycopg import OperationalError

from app.database import pool
from app.interview import engine

TOPICS = ["Ethics & Values"]


@pytest.fixture(scope="module", autouse=True)
def db():
    try:
        pool.open(wait=True, timeout=3)
        with pool.connection() as conn:
            if not conn.execute("SELECT count(*) AS n FROM questions").fetchone()["n"]:
                pytest.skip("no questions ingested")
    except (OperationalError, Exception) as e:   # no database available
        pytest.skip(f"database unavailable: {e}")
    yield
    pool.close()


def stub(scores: dict, verdict: str, follow_up: str | None):
    def fake(model, messages, schema, name):
        assert model == engine.EVALUATION_MODEL
        return {"scores": scores, "verdict": verdict, "critique": "", "missing_points": [],
                "model_answer_points": [], "follow_up_question": follow_up}
    return fake


def answer(sid):
    return engine.answer(sid, "An answer.", "coach", TOPICS, None, None, "past")


def test_good_answers_get_at_most_two_follow_ups(monkeypatch):
    monkeypatch.setattr(engine, "complete_json", stub({k: 4 for k in engine.SCORE_KEYS}, "good", "Example?"))
    sid, first = engine.next_question(None, TOPICS, None, None, "past")
    depths = [answer(sid)["next"]["depth"] for _ in range(3)]
    assert depths == [1, 2, 0]                       # follow-up, follow-up, then a new main question


def test_good_verdict_with_a_low_score_is_downgraded(monkeypatch):
    scores = {k: 5 for k in engine.SCORE_KEYS} | {"depth": 2}
    monkeypatch.setattr(engine, "complete_json", stub(scores, "good", "Why?"))
    sid, _ = engine.next_question(None, TOPICS, None, None, "past")
    r = answer(sid)
    assert r["evaluation"]["verdict"] == "partial" and r["next"]["depth"] == 0


def test_weak_answer_moves_on(monkeypatch):
    monkeypatch.setattr(engine, "complete_json", stub({k: 1 for k in engine.SCORE_KEYS}, "weak", None))
    sid, first = engine.next_question(None, TOPICS, None, None, "past")
    nxt = answer(sid)["next"]
    assert nxt["depth"] == 0 and nxt["main_index"] == first["main_index"] + 1
