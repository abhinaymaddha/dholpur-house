"""HTTP API through FastAPI's TestClient against the test database."""

import json

import pytest

from app.config import settings
from app.dependencies import get_retriever
from app.errors import ConfigError, ProviderError
from app.interview import evaluator
from app.services import ingest_job


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_search_facets_transcript_stats(client):
    r = client.get("/api/search", params={"q": "chess", "sort": "relevance", "limit": 5})
    assert r.status_code == 200 and r.json()["total"] == 1 and r.json()["hits"][0]["id"] == "u20"
    r = client.get("/api/search", params=[("topic", "Health"), ("topic", "Education"), ("has_marks", "true")])
    assert [h["id"] for h in r.json()["hits"]] == ["u14"]
    assert client.get("/api/search", params={"limit": 0}).status_code == 422
    f = client.get("/api/facets", params={"state": "Bihar"}).json()
    assert f["total"] == 1 and f["tree"]
    t = client.get("/api/transcripts/u14").json()
    assert t["board"] == "Sujata Chaturvedi" and t["telegram_url"].endswith("/14")
    assert client.get("/api/transcripts/nope").status_code == 404
    s = client.get("/api/stats").json()
    assert s["transcripts"] == 4 and s["llm_model"] == "fake-ask"


def events(text: str) -> list[tuple[str, object]]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_ask_streams_sources_then_answer(client, fake_llm):
    r = client.post("/api/ask", json={"question": "What was asked about Nalanda?", "top_k": 2})
    got = events(r.text)
    assert r.headers["content-type"].startswith("text/event-stream")
    assert got[0][0] == "sources" and got[0][1][0]["id"] == "u20"
    assert "".join(d for e, d in got if e == "delta") == "An answer citing [S1]." and got[-1] == ("done", {})


def test_ask_with_no_sources(client):
    got = events(client.post("/api/ask", json={"question": "anything", "q": "zzzqqq"}).text)
    assert got == [("sources", []), ("error", "No transcripts matched. Try different words or remove filters.")]


def test_ask_reports_provider_failures(client, fake_llm):
    fake_llm.error = ProviderError("rate limited")
    got = events(client.post("/api/ask", json={"question": "Nalanda"}).text)
    assert got[-1] == ("error", "rate limited")


def test_ask_uses_the_injected_retriever(client):
    class Stub:
        def retrieve(self, question, filters, top_k, q):
            return []
    client.app.dependency_overrides[get_retriever] = lambda: Stub()
    assert events(client.post("/api/ask", json={"question": "anything"}).text)[0] == ("sources", [])


def test_interview_flow(client, fake_llm):
    topics = {t["name"]: t for t in client.get("/api/interview/topics").json()}
    assert topics["Health"]["past_questions"] >= 1 and topics["DAF & Background"]["needs_daf"]
    filters = {"topics": ["Ethics & Values"], "question_mode": "real"}
    first = client.post("/api/interview/next", json={"filters": filters}).json()
    sid = first["session_id"]
    fake_llm.json["evaluation"] = lambda m: {
        "scores": {k: 4 for k in evaluator.SCORE_KEYS}, "verdict": "good", "issues": [], "strengths": [],
        "critique": "", "missing_points": [], "model_answer_points": [], "follow_up_question": "Why?"}
    r = client.post("/api/interview/answer", json={"session_id": sid, "answer": "Because.", "filters": filters})
    assert r.status_code == 200 and r.json()["next"]["depth"] == 1
    turns = client.get(f"/api/interview/sessions/{sid}").json()
    assert len(turns) == 2 and turns[0]["answer"] == "Because."
    assert client.get(f"/api/interview/sessions/{sid}/report").json()["answered"] == 1
    similar = client.get(f"/api/interview/turns/{first['turn']['id']}/similar").json()
    assert similar and all(s["transcript_id"] != first["turn"]["source"]["transcript_id"] for s in similar)


def test_interview_errors(client, fake_llm):
    r = client.post("/api/interview/next", json={"filters": {"topics": []}})
    assert r.status_code == 400 and r.json()["detail"] == "Pick at least one topic to be asked about"
    sid = client.post("/api/interview/next", json={"filters": {"topics": ["Health"], "question_mode": "real"}}
                      ).json()["session_id"]
    fake_llm.error = ProviderError("bad JSON")
    r = client.post("/api/interview/answer", json={"session_id": sid, "answer": "x", "filters": {"topics": ["Health"]}})
    assert r.status_code == 502 and r.json()["detail"] == "The AI model failed: bad JSON"
    fake_llm.error = ConfigError("No API key")
    r = client.post("/api/interview/next", json={"session_id": sid, "filters": {"topics": ["Health"]}})
    assert r.status_code == 500 and r.json()["detail"] == "No API key"
    assert client.get("/api/interview/sessions/00000000-0000-0000-0000-000000000000/report").status_code == 404
    assert client.get("/api/interview/turns/999999/similar").status_code == 404
    assert client.post("/api/interview/answer", json={"session_id": sid, "answer": "", "filters": {}}).status_code == 422


# ---------- admin ----------

@pytest.fixture
def admin(monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "s3cret")
    monkeypatch.setattr(ingest_job, "run_ingest", lambda source, log: {"transcripts": 1})
    return {"Authorization": "Bearer s3cret"}


def test_admin_disabled_without_token(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "")
    assert client.get("/api/admin/ingest").status_code == 404


def test_admin_rejects_wrong_token(client, admin):
    assert client.get("/api/admin/ingest", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/api/admin/ingest", headers={"Authorization": "Basic s3cret"}).status_code == 401


def test_admin_upload_flow(client, admin):
    bad = client.post("/api/admin/ingest", headers=admin, files={"files": ("../evil.sh", b"x")})
    assert bad.status_code == 422
    ok = client.post("/api/admin/ingest", headers=admin, files={"files": ("messages.html", b"<html></html>")})
    assert ok.status_code == 202 and ok.json()["files"] == ["messages.html"]
    for _ in range(500):
        if client.get("/api/admin/ingest", headers=admin).json()["state"] != "running":
            break
    assert client.get("/api/admin/ingest", headers=admin).json()["summary"] == {"transcripts": 1}


def test_admin_upload_while_running(client, admin, monkeypatch):
    monkeypatch.setattr(ingest_job, "status", lambda: {"state": "running"})
    r = client.post("/api/admin/ingest", headers=admin, files={"files": ("messages.html", b"x")})
    assert r.status_code == 409


def test_admin_upload_race_cleans_up(client, admin, monkeypatch):
    from app.errors import IngestRunning
    saved = []

    def start(folder, label, cleanup):
        saved.append(folder)
        raise IngestRunning("busy")
    monkeypatch.setattr(ingest_job, "start", start)
    r = client.post("/api/admin/ingest", headers=admin, files={"files": ("messages2.html", b"x")})
    assert r.status_code == 409 and not saved[0].exists()


def test_admin_upload_size_limit(client, admin, monkeypatch):
    from app.api.routes import admin as admin_routes
    monkeypatch.setattr(admin_routes, "MAX_FILE_BYTES", 10)
    r = client.post("/api/admin/ingest", headers=admin, files={"files": ("messages.html", b"x" * 2_000_000)})
    assert r.status_code == 413


def test_admin_news_refresh(client, admin, monkeypatch):
    from app.dependencies import get_news

    class Stub:
        def refresh(self, force):
            return {"forced": force}
    client.app.dependency_overrides[get_news] = lambda: Stub()
    assert client.post("/api/admin/news/refresh", headers=admin).json() == {"forced": True}
