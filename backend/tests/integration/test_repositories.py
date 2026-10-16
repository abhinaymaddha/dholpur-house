"""Repositories against the synthetic data ingested by conftest (4 transcripts: u10 Rajasthan / Sheel Vardhan,
u14 Kerala / Sujata, u20 Bihar / Raj Shukla, u21 Haryana / Sanjay Verma; u12 held)."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.repositories import (
    ChunkRepository, InterviewRepository, NewsRepository, QuestionRepository, TranscriptRepository,
)
from app.repositories.filters import filter_sql
from app.repositories.transcripts import HL_END, HL_START
from app.schemas.filters import TranscriptFilters
from app.services.embeddings import embed_one

ANY = TranscriptFilters()


@pytest.fixture
def transcripts():
    return TranscriptRepository()


# ---------- filters ----------

def test_filter_sql_builds_only_the_set_conditions():
    assert filter_sql(ANY) == ("TRUE", {})
    where, params = filter_sql(TranscriptFilters(board="B", topics=["Economy"], has_marks=True), skip=("board",), q=" gdp ")
    assert "t.board" not in where and "t.topics @>" in where and "pt_marks IS NOT NULL" in where
    assert params == {"topics": ["Economy"], "has_marks": True, "q": "gdp"}


# ---------- transcripts ----------

def test_listing_without_keywords_is_newest_first(transcripts):
    total, rows = transcripts.search("", ANY, limit=10, offset=0)
    assert total == 4 and [r["id"] for r in rows] == ["u21", "u20", "u10", "u14"]
    assert rows[0]["rank"] is None and len(rows[0]["snippet"]) <= 320


def test_keyword_search_highlights_and_ranks(transcripts):
    total, rows = transcripts.search("dharma", ANY, limit=10, offset=0)
    assert total == 1 and rows[0]["id"] == "u21"
    assert f"{HL_START}dharma{HL_END}" in rows[0]["snippet"].lower()
    total, _ = transcripts.search('"solar energy" OR Nalanda', ANY, limit=10, offset=0)
    assert total == 2


@pytest.mark.parametrize("sort, first", [("recent", "u21"), ("questions", "u10"), ("marks", "u21"),
                                         ("relevance", "u21")])
def test_sorts(transcripts, sort, first):
    _, rows = transcripts.search("", ANY, limit=10, offset=0, sort=sort)
    assert rows[0]["id"] == first


def test_keyword_search_with_explicit_sort_and_paging(transcripts):
    total, rows = transcripts.search("district", ANY, limit=1, offset=1, sort="recent")
    assert total >= 2 and len(rows) == 1


def test_search_with_no_match(transcripts):
    assert transcripts.search("zzzqqq", ANY, limit=5, offset=0) == (0, [])


@pytest.mark.parametrize("f, ids", [
    (TranscriptFilters(board="Sujata Chaturvedi"), {"u14"}),
    (TranscriptFilters(cse_year=2023), {"u14"}),
    (TranscriptFilters(exam="CSE", has_marks=True), {"u14", "u21"}),
    (TranscriptFilters(state="Bihar"), {"u20"}),
    (TranscriptFilters(optional_tag="Economics"), {"u10"}),
    (TranscriptFilters(background="Medical"), {"u14"}),
    (TranscriptFilters(interest="Chess"), {"u20"}),
    (TranscriptFilters(topics=["Health", "Education"]), {"u14"}),
])
def test_filters(transcripts, f, ids):
    _, rows = transcripts.search("", f, limit=10, offset=0)
    assert {r["id"] for r in rows} == ids


def test_facets_ignore_their_own_selection(transcripts):
    f = transcripts.facets(TranscriptFilters(state="Kerala"))
    assert f["total"] == 1
    states = {s["value"] for s in f["state"]}
    assert {"Kerala", "Bihar", "Rajasthan", "Haryana"} <= states   # siblings stay visible
    assert f["has_marks"] == 1 and [e["value"] for e in f["exam"]] == ["CSE"]
    years = {y["year"]: y for y in f["tree"]}
    assert years[2023]["boards"] == [{"value": "Sujata Chaturvedi", "count": 1}]


def test_facets_within_keywords(transcripts):
    f = transcripts.facets(ANY, q="dharma")
    assert f["total"] == 1 and f["tree"][0]["boards"][0]["value"] == "Sanjay Verma"


def test_get_meta_stats(transcripts):
    t = transcripts.get("u14")
    assert t["board"] == "Sujata Chaturvedi" and t["structure"]["sections"]
    assert "[email removed]" in t["text"] and "[phone removed]" in t["text"] and "9000012345" not in t["text"]
    assert transcripts.get("nope") is None
    assert set(transcripts.meta(["u10", "u20", "x"])) == {"u10", "u20"}
    s = transcripts.stats()
    assert (s["transcripts"], s["held"]) == (4, 1) and s["chunks"] > 4
    assert {b["value"] for b in s["boards"]} >= {"Sanjay Verma"} and s["years"][0] == {"value": "2024", "count": 3}
    assert transcripts.ping() and not transcripts.is_empty() and not TranscriptRepository.prepare_database()


# ---------- chunks ----------

def test_chunks_nearest_and_keyword_respect_filters():
    chunks = ChunkRepository()
    near = chunks.nearest(embed_one("chess teaching school governance migration Bihar"), ANY, limit=3)
    assert near[0]["transcript_id"] == "u20"
    only_kerala = chunks.nearest(embed_one("chess"), TranscriptFilters(state="Kerala"), limit=50)
    assert {c["transcript_id"] for c in only_kerala} == {"u14"}
    kw = chunks.keyword("nalanda OR champaran", ANY, limit=5)
    assert kw and all(c["transcript_id"] == "u20" for c in kw)
    assert chunks.keyword("", ANY, limit=5) == []
    assert all(c["transcript_id"] != "u20" for c in chunks.keyword("nalanda", ANY, 5, exclude=("u20",)))
    assert chunks.nearest(embed_one("chess"), ANY, 5, q="dharma", exclude=("u21",)) == []


# ---------- questions ----------

def test_questions_nearest_with_follow_up_and_exclusions():
    questions = QuestionRepository()
    vec = embed_one("Why do you read the Gita and when did you start it?")
    best = questions.nearest(vec, 3)[0]
    assert best["transcript_id"] == "u21" and best["follow_up"].startswith("What is your understanding of dharma")
    assert best["distance"] < 0.05
    others = questions.nearest(vec, 3, exclude_ids=[best["id"]], exclude_transcript="u10", board="Sanjay Verma")
    assert best["id"] not in {r["id"] for r in others} and {r["board"] for r in others} == {"Sanjay Verma"}
    assert all(r["text"].rstrip().endswith("?") or len(r["text"].split()) >= 5
               for r in questions.nearest(vec, 20, askable=True))


def test_questions_samples_and_counts():
    questions = QuestionRepository()
    sample = questions.board_sample("Lt Gen Raj Shukla", 4)
    assert len(sample) == 4 and {r["board"] for r in sample} == {"Lt Gen Raj Shukla"}
    counts = questions.topic_counts()
    assert counts["Health"] >= 3 and counts["International Relations"] >= 2
    assert len(questions.of_transcript("u14", n=5)) == 5


def test_profile_matches_prefers_the_same_state():
    profile = {"background": ["Medical"], "states": ["Kerala"], "interests": [], "optional_tag": "Sociology"}
    best = QuestionRepository().profile_matches(profile, n=1)[0]
    assert best["id"] == "u14" and best["score"] >= 5


# ---------- interviews ----------

def test_interview_turn_lifecycle():
    repo = InterviewRepository()
    sid = repo.create_session()
    assert repo.session_exists(sid) and not repo.session_exists(uuid4())
    t1 = repo.add_turn(sid, 1, 0, "Economy", "What is GDP?", {"type": "past", "question_id": 1})
    t2 = repo.add_turn(sid, 1, 1, "Economy", "Why?", {"type": "followup"})
    repo.save_answer(t1["id"], "An answer", {"verdict": "good"}, "coach")
    repo.mark_skipped(t2["id"])
    turns = repo.turns(sid)
    assert [t["id"] for t in turns] == [t1["id"], t2["id"]]
    assert turns[0]["answer"] == "An answer" and turns[0]["mode"] == "coach"
    assert repo.turn(t2["id"])["evaluation"] == {"skipped": True} and repo.turn(-1) is None


# ---------- news ----------

def test_news_save_recent_prune(sql):
    sql("TRUNCATE news_items, news_fetches")
    repo = NewsRepository()
    now = datetime.now(timezone.utc)
    items = [(f"https://n.test/{i}", "World", f"Story {i}", "s", now - timedelta(days=i), topics)
             for i, topics in enumerate([["Economy"], ["Economy", "International Relations"], ["Health"]])]
    repo.save_feed("World", items, now)
    repo.save_feed("World", [(items[0][0], "World", "Story 0 (updated)", "s2", items[0][4], ["Economy"])], now)
    assert set(repo.fetch_times()) == {"World"}
    recent = repo.recent(["Economy"], limit=5)
    assert [r["title"] for r in recent] == ["Story 0 (updated)", "Story 1"]
    assert [r["url"] for r in repo.recent(["Economy"], exclude_urls=[items[0][0]])] == [items[1][0]]
    assert repo.topic_counts() == {"Economy": 2, "International Relations": 1, "Health": 1}
    repo.prune(now - timedelta(days=1, hours=12))
    assert repo.topic_counts() == {"Economy": 2, "International Relations": 1}
    sql("TRUNCATE news_items, news_fetches")
