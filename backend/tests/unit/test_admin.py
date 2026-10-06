import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import admin
from app.config import settings
from app.services import ingest_job


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(ingest_job, "run_ingest", lambda source, log: {"transcripts": 1})
    app = FastAPI()
    app.include_router(admin.router)
    return TestClient(app)


def test_admin_disabled_without_token(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "")
    assert client.get("/api/admin/ingest").status_code == 404


def test_admin_rejects_wrong_token(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "s3cret")
    assert client.get("/api/admin/ingest", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_admin_only_accepts_export_files(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "s3cret")
    auth = {"Authorization": "Bearer s3cret"}
    bad = client.post("/api/admin/ingest", headers=auth, files={"files": ("../evil.sh", b"x")})
    assert bad.status_code == 422
    ok = client.post("/api/admin/ingest", headers=auth, files={"files": ("messages.html", b"<html></html>")})
    assert ok.status_code == 202 and ok.json()["files"] == ["messages.html"]
