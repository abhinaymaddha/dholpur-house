"""Services on top of the repositories: hybrid retrieval, the question bank, news, Ask, ingest jobs."""

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import feedparser
import numpy as np
import pytest
import requests

from app.dependencies import get_bank, get_news, get_retriever
from app.errors import IngestRunning
from app.interview.bank import QuestionBank, fmt, fmt_candidates, readable
from app.repositories import NewsRepository, QuestionRepository
from app.schemas.filters import TranscriptFilters
from app.services import answer, embeddings, ingest_job
from app.services.news import NewsService, _clean, _published
from app.services.retrieval import HybridRetriever

ANY = TranscriptFilters()


# ---------- retrieval ----------

def test_keyword_query_drops_stopwords():
    assert HybridRetriever.keyword_query("What did boards ask about the Agniveer scheme?") == "agniveer OR scheme"


def test_transcript_score_rewards_more_matching_chunks():
    assert HybridRetriever.transcript_score([0.5]) == 0.5
    assert HybridRetriever.transcript_score([0.5, 0.2, 0.2]) == pytest.approx(0.6)


def test_fuse_groups_by_transcript():
    r = get_retriever()
    a = [{"id": 1, "transcript_id": "t1"}, {"id": 2, "transcript_id": "t2"}]
    b = [{"id": 2, "transcript_id": "t2"}]
    grouped = r.fuse(a, b)
    assert grouped["t2"][0][0] > grouped["t1"][0][0]


def test_retrieve_returns_transcripts_with_excerpts():
    results = get_retriever().retrieve("Nalanda university and the Champaran satyagraha", ANY, top_k=2,
                                       chunks_per_transcript=2)
    assert results[0]["id"] == "u20" and results[0]["board"] == "Lt Gen Raj Shukla"
    assert 1 <= len(results[0]["excerpts"]) <= 2 and results[0]["score"] > 0
    seqs = [e["section"] for e in results[0]["excerpts"]]
    assert seqs == sorted(seqs, key=lambda s: [e["section"] for e in results[0]["excerpts"]].index(s))


def test_retrieve_with_filters_and_nothing_found():
    assert {r["id"] for r in get_retriever().retrieve("health", TranscriptFilters(state="Kerala"))} == {"u14"}
    assert get_retriever().retrieve("anything", ANY, q="zzzqqq") == []


# ---------- question bank ----------

def test_readable_and_formatting():
    assert readable("(Then shifted to polity) What is federalism?") == "What is federalism?"
    rows = [{"text": "Q1?", "cse_year": 2024, "board": "B", "follow_up": "F?"}]
    assert fmt(rows) == "- Q1?  _(CSE 2024, B board)_\n  - then: F?"
    assert fmt(rows, with_follow_up=False).count("\n") == 0 and fmt([]) == "- (none found)"
    cand = [{"daf": None, "board": "B", "cse_year": 2024, "questions": [{"member": "M1", "text": "Q?"}]}]
    assert "DAF: n/a" in fmt_candidates(cand) and fmt_candidates([]) == "(no close profile match)"


def test_similar_merges_queries_dedupes_and_mixes_in_the_board():
    bank = get_bank()
    rows = bank.similar(["What is the significance of Nalanda university", "army disaster relief"], n=6)
    assert rows[0]["transcript_id"] == "u20" and len(rows) <= 6
    assert len({r["text"].lower()[:60] for r in rows}) == len(rows)
    with_board = bank.similar(["solar energy policy"], n=8, board="Sujata Chaturvedi")
    assert "Sujata Chaturvedi" in {r["board"] for r in with_board}
    assert bank.similar([]) == []


def test_similar_dedupes_identical_wording():
    row = {"id": 1, "text": "Same question?", "distance": 0.2}
    repo = SimpleNamespace(nearest=lambda vec, n, **kw: [row, {**row, "id": 2, "distance": 0.1}, {**row, "distance": 0.3}])
    bank = QuestionBank(repo, embedder=lambda qs: [None for _ in qs])
    assert [r["id"] for r in bank.similar(["x"])] == [2]


def test_similar_candidates_and_board_examples():
    bank = get_bank()
    cands = bank.similar_candidates("Kerala, MBBS, Sociology")
    assert cands[0]["id"] == "u14" and cands[0]["questions"]
    assert bank.similar_candidates("nothing recognisable here") == []
    assert {r["board"] for r in bank.board_examples("Sanjay Verma", 3)} == {"Sanjay Verma"}
    assert bank.topic_counts()["Health"] >= 1


# ---------- news ----------

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>India and China agree on border patrolling</title><link>https://n.test/a</link>
<description>&lt;p&gt;Talks on the border &amp;amp; trade&lt;/p&gt;</description>
<pubDate>Mon, 12 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>RBI keeps the repo rate unchanged</title><link>https://n.test/b</link><description>inflation</description></item>
<item><title>A recipe for mango pickle</title><link>https://n.test/c</link></item>
<item><title></title><link>https://n.test/d</link></item>
</channel></rss>"""


@pytest.fixture
def news(sql, monkeypatch):
    sql("TRUNCATE news_items, news_fetches")

    def fake_fetch(url):
        if "broken" in url:
            raise requests.ConnectionError("unreachable")
        return feedparser.parse(RSS.replace("https://n.test/", url + "#"))
    service = NewsService(NewsRepository())
    monkeypatch.setattr(service, "fetch", fake_fetch)
    yield service
    sql("TRUNCATE news_items, news_fetches")


def test_refresh_tags_articles_and_respects_feed_topics(news):
    report = news.refresh()
    assert report["World"] == 2 and report["National"] == 2 and report["Broken"].startswith("error")
    world = news.recent(["International Relations"], limit=10)
    assert {a["source"] for a in world} == {"World", "National"}
    assert world[0]["summary"] == "Talks on the border & trade"
    assert news.topic_counts()["Economy"] == 2
    assert news.refresh() == {"Broken": "error: unreachable"}   # fresh feeds are skipped until refresh_hours pass
    assert set(news.refresh(force=True)) == {"World", "National", "Broken"}


def test_refresh_in_background_swallows_errors(news, monkeypatch):
    monkeypatch.setattr(news, "refresh", lambda: 1 / 0)
    news.refresh_in_background().join(timeout=5)   # no exception escapes the thread


def test_news_helpers():
    assert _clean("<b>A</b>&amp;\n B") == "A & B"
    assert _published({"published_parsed": time.struct_time((2026, 1, 2, 3, 4, 5, 0, 0, 0))}) == \
        datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert _published({}).tzinfo is timezone.utc
    assert NewsService.topics_for("RBI and China", ["Economy"]) == ["Economy"]
    assert set(NewsService.topics_for("RBI and China", None)) == {"Economy", "International Relations"}
    assert get_news().sources()["refresh_hours"] == 6


def test_fetch_uses_requests(monkeypatch):
    seen = {}

    class R:
        content = RSS.encode()

        def raise_for_status(self):
            pass

    monkeypatch.setattr(requests, "get", lambda url, headers, timeout: seen.update(url=url) or R())
    assert len(NewsService.fetch("https://feeds.test/x").entries) == 4 and seen["url"] == "https://feeds.test/x"


def test_default_sources_file(monkeypatch):
    from app.services import news as news_module
    monkeypatch.setattr(news_module.settings, "sources_file", None)
    assert NewsService(NewsRepository()).sources_file == news_module.DEFAULT_FILE


# ---------- Ask ----------

def test_answer_builds_numbered_sources(fake_llm):
    sources = [{"board": "B", "cse_year": 2024, "exam": "CSE", "interview_date": None, "daf": "Kerala",
                "optional_subject": None, "pt_marks": 180, "excerpts": [{"text": "Q1"}, {"text": "Q2"}]}]
    context = answer.build_context(sources)
    assert context.startswith("[S1] Board: B | CSE 2024 (CSE) | Interview date: n/a | DAF: Kerala") and \
        "PT marks: 180" in context and "Q1\n...\nQ2" in context
    assert "".join(answer.stream_answer("Who?", sources)) == "An answer citing [S1]."
    sent = fake_llm.calls[0]["messages"]
    assert sent[0]["role"] == "system" and sent[1]["content"].endswith("Question: Who?")


# ---------- embeddings ----------

def test_embed_helpers_use_the_model():
    vecs = embeddings.embed(["a b", "c"])
    assert len(vecs) == 2 and np.isclose(np.linalg.norm(embeddings.embed_one("a")), 1)


def test_model_loader(monkeypatch):
    from tests.conftest import REAL_EMBED_MODEL
    built = {}

    class TextEmbedding:
        def __init__(self, name, cache_dir):
            built.update(name=name, cache_dir=cache_dir)
    monkeypatch.setitem(sys.modules, "fastembed", SimpleNamespace(TextEmbedding=TextEmbedding))
    REAL_EMBED_MODEL.cache_clear()
    assert isinstance(REAL_EMBED_MODEL(), TextEmbedding) and built["name"].endswith("MiniLM-L12-v2")
    REAL_EMBED_MODEL.cache_clear()


# ---------- ingest jobs ----------

def wait_for(state, timeout=5):
    deadline = time.time() + timeout
    while ingest_job.status()["state"] == "running" and time.time() < deadline:
        time.sleep(0.01)
    assert ingest_job.status()["state"] == state


def test_ingest_job_runs_in_the_background_and_cleans_up(monkeypatch, tmp_path):
    gate = []

    def fake_run(source, log):
        while not gate:
            time.sleep(0.01)
        log("loaded")
        return {"transcripts": 1}
    monkeypatch.setattr(ingest_job, "run_ingest", fake_run)
    folder = tmp_path / "upload"
    folder.mkdir()
    ingest_job.start(folder, "upload: x", cleanup=folder)
    with pytest.raises(IngestRunning):
        ingest_job.start(folder, "again")
    assert ingest_job.status()["source"] == "upload: x"
    gate.append(1)
    wait_for("done")
    status = ingest_job.status()
    assert status["summary"] == {"transcripts": 1} and status["log"] == ["loaded"] and "finished_at" in status
    assert not folder.exists()


def test_ingest_job_failure_is_reported(monkeypatch):
    monkeypatch.setattr(ingest_job, "run_ingest", lambda source, log: 1 / 0)
    ingest_job.start(Path("/nonexistent"), "bad")
    wait_for("failed")
    assert "division by zero" in ingest_job.status()["error"]
