"""Interview mode: question sources, the follow-up policy and the report, with the LLM faked."""

import random
from datetime import datetime, timezone

import pytest

from app.dependencies import get_bank, get_interviews, get_news, get_question_sources
from app.errors import InterviewError
from app.interview import evaluator, prompts
from app.interview.questions import (
    ANGLES, GeneratedQuestionSource, QuestionContext, RealQuestionSource, daf_items,
)
from app.interview.session import MAX_FOLLOWUPS, Filters, InterviewSession, _context, _reference
from app.repositories import NewsRepository

ETHICS = ["Ethics & Values"]
DAF = "Kerala, MBBS, Government Medical College, reading novels"


def evaluation(score=4, verdict="good", follow_up="And if your senior insisted?"):
    def reply(messages):
        return {"scores": {k: score for k in evaluator.SCORE_KEYS}, "verdict": verdict, "issues": [],
                "strengths": ["clear"], "critique": "ok", "missing_points": [], "model_answer_points": [],
                "follow_up_question": follow_up}
    return reply


def written(question="As a doctor from Kerala, how would you fix rural health care?", angle="daf",
            daf_item="MBBS", article_url=None):
    def reply(messages):
        return {"question": question, "angle": angle, "daf_item": daf_item, "based_on": "the DAF",
                "article_url": article_url}
    return reply


def new_session():
    return InterviewSession.open(None, get_interviews(), get_bank(), get_question_sources())


def topic(name):
    return prompts.topic(name)


# ---------- helpers and angle choice ----------

def test_daf_items_split_on_separators():
    assert daf_items("Kerala, MBBS; novels | chess\nx\n") == ["Kerala", "MBBS", "novels", "chess"]


@pytest.mark.parametrize("name, daf, has_articles, expected", [
    ("DAF & Background", DAF, False, ["daf_depth", "daf_admin", "daf_depth"]),
    ("Economy", DAF, True, ["daf_link", "news_daf", "topic"]),
    ("Economy", DAF, False, ["daf_link", "topic", "daf_link"]),
    ("Economy", None, True, ["news", "topic", "news"]),
    ("Ethics & Values", None, False, ["topic", "topic", "topic"]),
])
def test_angles_rotate_by_questions_asked_on_the_topic(name, daf, has_articles, expected):
    got = []
    turns = []
    for _ in expected:
        ctx = QuestionContext(topic=topic(name), board=None, daf=daf, turns=turns)
        got.append(GeneratedQuestionSource.angle(ctx, has_articles))
        turns = turns + [{"topic": name, "depth": 0, "question": "q", "source": {}}]
    assert got == expected and set(got) <= set(ANGLES)


def test_context_properties():
    turns = [{"topic": "Economy", "depth": 0, "question": "Q1?", "source": {"question_id": 5, "examples": [1, 2]}},
             {"topic": "Economy", "depth": 1, "question": "Q2?", "source": {"url": "https://n/1", "daf_item": "MBBS"}}]
    ctx = QuestionContext(topic=topic("Economy"), board=None, daf=None, turns=turns)
    assert ctx.used_question_ids == [5, 1, 2] and ctx.used_urls == ["https://n/1"]
    assert ctx.covered_daf_items == ["MBBS"] and ctx.asked == "- Q1?\n- Q2?" and ctx.asked_on_topic == 1
    assert QuestionContext(topic=topic("Economy"), board=None, daf=None).asked == "- (nothing yet)"


# ---------- sources ----------

def test_real_source_asks_a_stored_question_without_the_llm(fake_llm):
    source = RealQuestionSource(get_bank(), rng=random.Random(1))
    question, src = source.next(QuestionContext(topic=topic("Health"), board=None, daf=DAF))
    assert src["type"] == "past" and src["transcript_id"] in {"u10", "u14", "u20", "u21"}
    assert question.endswith("?") and fake_llm.calls == []


def test_real_source_with_nothing_left(fake_llm):
    source = RealQuestionSource(type("Empty", (), {"similar": lambda self, *a, **k: []})())
    with pytest.raises(InterviewError, match="No past questions"):
        source.next(QuestionContext(topic=topic("Health"), board=None, daf=None))


def test_generated_question_without_daf_uses_the_general_prompt(fake_llm):
    fake_llm.json["question"] = written("What is the role of integrity in administration?", "topic", None)
    question, src = get_question_sources()["generated"].next(
        QuestionContext(topic=topic("Ethics & Values"), board="Sanjay Verma", daf=None))
    prompt = fake_llm.calls[0]["messages"][0]["content"]
    assert fake_llm.calls[0]["model"] == "model_2" and "The Sanjay Verma board" in prompt
    assert question.startswith("What is the role") and src["type"] == "generated" and src["target_angle"] == "topic"
    assert src["examples"] and "url" not in src


def test_generated_question_with_daf_uses_the_daf_prompt(fake_llm):
    fake_llm.json["question"] = written()
    ctx = QuestionContext(topic=topic("Health"), board=None, daf=DAF,
                          turns=[{"topic": "Ethics & Values", "depth": 0, "question": "Earlier?",
                                  "source": {"daf_item": "Kerala"}}])
    _, src = get_question_sources()["generated"].next(ctx)
    prompt = fake_llm.calls[0]["messages"][0]["content"]
    assert "- MBBS" in prompt and "Kerala" in prompt and "A typical UPSC board" in prompt
    assert "Candidate with DAF" in prompt   # the closest real profile (u14) is shown
    assert src["daf_item"] == "MBBS" and src["target_angle"] == "daf_link"


def test_generated_question_on_a_news_item_records_the_article(fake_llm, sql):
    sql("TRUNCATE news_items, news_fetches")
    NewsRepository().save_feed("World", [("https://n.test/border", "World", "India and China agree on border talks",
                                          "Patrolling resumes.", datetime.now(timezone.utc),
                                          ["International Relations"])], datetime.now(timezone.utc))
    fake_llm.json["question"] = written("What do the border talks mean for India?", "news", None,
                                        "https://n.test/border")
    _, src = get_question_sources()["generated"].next(
        QuestionContext(topic=topic("International Relations"), board=None, daf=None))
    assert src["url"] == "https://n.test/border" and src["publisher"] == "World" and src["title"].startswith("India")
    assert "India and China agree" in fake_llm.calls[0]["messages"][0]["content"]
    sql("TRUNCATE news_items, news_fetches")


# ---------- session policy ----------

def test_good_answers_get_at_most_two_follow_ups(fake_llm):
    fake_llm.json["evaluation"] = evaluation()
    session = new_session()
    filters = Filters(topics=ETHICS, question_mode="real")
    first = session.next_question(filters)
    depths = [session.answer("An answer.", "coach", filters)["next"]["depth"] for _ in range(MAX_FOLLOWUPS + 1)]
    assert depths == [1, 2, 0] and first["depth"] == 0     # follow-up, follow-up, then a new main question
    followup = session.turns[1]
    assert followup["question"] == "And if your senior insisted?" and followup["source"] == {"type": "followup"}


def test_good_verdict_with_a_low_score_is_downgraded_and_moves_on(fake_llm):
    fake_llm.json["evaluation"] = lambda m: {**evaluation(5)(m), "scores": {**{k: 5 for k in evaluator.SCORE_KEYS},
                                                                            "depth": 2}}
    session = new_session()
    filters = Filters(topics=ETHICS, question_mode="real")
    session.next_question(filters)
    r = session.answer("An answer.", "exam", filters)
    assert r["evaluation"]["verdict"] == "partial" and r["next"]["depth"] == 0 and r["next"]["main_index"] == 2


def test_weak_answer_moves_on_to_the_next_chosen_topic(fake_llm):
    fake_llm.json["evaluation"] = evaluation(1, "weak", None)
    session = new_session()
    filters = Filters(topics=["Ethics & Values", "Health", "Not a topic"], question_mode="real")
    first = session.next_question(filters)
    nxt = session.answer("Not sure.", "coach", filters)["next"]
    assert (first["topic"], nxt["topic"]) == ("Ethics & Values", "Health")


def test_asking_again_skips_the_open_question(fake_llm):
    session = new_session()
    filters = Filters(topics=ETHICS, question_mode="real")
    session.next_question(filters)
    session.next_question(filters)
    first, second = session.turns
    assert first["evaluation"] == {"skipped": True} and session.pending()["id"] == second["id"]


def test_answer_without_an_open_question():
    session = new_session()
    with pytest.raises(InterviewError, match="no open question"):
        session.answer("x", "coach", Filters(topics=ETHICS))


def test_topic_and_daf_requirements():
    session = new_session()
    with pytest.raises(InterviewError, match="Pick at least one topic"):
        session.next_question(Filters(topics=["Nope"]))
    with pytest.raises(InterviewError, match="Add your DAF"):
        session.next_question(Filters(topics=["DAF & Background"], daf="  "))


def test_open_resumes_known_sessions_and_replaces_unknown_ones():
    session = new_session()
    assert InterviewSession.open(session.id, get_interviews(), get_bank(), get_question_sources()).id == session.id
    from uuid import uuid4
    assert InterviewSession.open(uuid4(), get_interviews(), get_bank(), get_question_sources()).id != session.id


def test_evaluator_sees_the_chain_and_the_news_reference(fake_llm, sql):
    fake_llm.json["evaluation"] = evaluation()
    repo = get_interviews()
    session = new_session()
    repo.add_turn(session.id, 1, 0, "Economy", "What does the RBI decision mean?",
                  {"type": "generated", "based_on": "news", "title": "RBI holds rates", "publisher": "World",
                   "published_at": "2026-10-12T10:00:00+00:00", "summary": "Repo unchanged."})
    session.answer("Rates stay to curb inflation.", "coach", Filters(topics=["Economy"]))
    prompt = fake_llm.calls[0]["messages"][0]["content"]
    assert "News item (World, 2026-10-12): RBI holds rates. Repo unchanged." in prompt
    assert "Candidate: Rates stay to curb inflation." in prompt


def test_context_and_reference_sentences():
    assert "real question asked in a past interview (CSE 2024, B board)" in _context(
        {"type": "past", "cse_year": 2024, "board": "B"})
    assert "builds on: DAF" in _context({"type": "generated", "based_on": "DAF"})
    assert _context({"type": "followup"}) == "This is a follow-up question."
    assert _reference([{"source": {"type": "past"}}]) == ""


# ---------- report ----------

def test_report_averages_by_dimension_and_topic(fake_llm):
    session = new_session()
    filters = Filters(topics=["Ethics & Values", "Health"], question_mode="real")
    session.next_question(filters)
    fake_llm.json["evaluation"] = evaluation(4, "good", None)
    session.answer("Good answer.", "coach", filters)
    fake_llm.json["evaluation"] = evaluation(2, "weak", None)
    session.answer("Weak answer.", "coach", filters)
    session.next_question(filters)                 # skips the open one
    # an older evaluation without the newer `tone` score still averages fine
    old = session.turns[0]
    get_interviews().save_answer(old["id"], old["answer"], {**old["evaluation"], "scores": {
        k: v for k, v in old["evaluation"]["scores"].items() if k != "tone"}}, "coach")
    report = session.report()
    assert report["answered"] == 2 and report["skipped"] == 1 and report["average"] == 3.0
    assert report["verdicts"] == {"good": 1, "partial": 0, "weak": 1}
    assert report["dimensions"]["tone"] == 2.0 and report["dimensions"]["depth"] == 3.0
    assert {t["topic"]: t["average"] for t in report["topics"]} == {"Ethics & Values": 4.0, "Health": 2.0}


def test_report_of_an_empty_session():
    report = new_session().report()
    assert report["answered"] == 0 and report["average"] == 0.0 and report["topics"] == []


def test_news_service_is_shared():
    assert get_news() is get_news()
