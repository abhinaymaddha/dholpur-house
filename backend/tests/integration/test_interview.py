"""Interview mode: question sources, the follow-up policy and the report, with the LLM faked."""

import random
import threading
import time
from datetime import datetime, timezone

import pytest

from app.dependencies import get_bank, get_interviews, get_news, get_question_sources
from app.errors import InterviewError
from app.interview import evaluator, prompts, session as session_module
from app.interview.background import BackgroundWork
from app.interview.questions import (
    ANGLES, OPENERS, GeneratedQuestionSource, QuestionContext, RealQuestionSource, daf_items,
)
from app.interview.session import MAX_FOLLOWUPS, Filters, InterviewSession, _context, _reference
from app.repositories import NewsRepository
from app.repositories.questions import CLEAN
from tests.fixtures.fakes import DeferredExecutor

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
    filters = Filters(plan="topics", topics=ETHICS, question_mode="real")
    first = session.next_question(filters)
    depths = [session.answer("An answer.", "coach", filters)["next"]["depth"] for _ in range(MAX_FOLLOWUPS + 1)]
    assert depths == [1, 2, 0] and first["depth"] == 0     # follow-up, follow-up, then a new main question
    followup = session.turns[1]
    assert followup["question"] == "And if your senior insisted?" and followup["source"] == {"type": "followup"}


def test_good_verdict_with_a_low_score_is_downgraded_and_moves_on(fake_llm):
    fake_llm.json["evaluation"] = lambda m: {**evaluation(5)(m), "scores": {**{k: 5 for k in evaluator.SCORE_KEYS},
                                                                            "depth": 2}}
    session = new_session()
    filters = Filters(plan="topics", topics=ETHICS, question_mode="real")
    session.next_question(filters)
    r = session.answer("An answer.", "exam", filters)
    assert r["evaluation"]["verdict"] == "partial" and r["next"]["depth"] == 0 and r["next"]["main_index"] == 2


def test_weak_answer_moves_on_to_the_next_chosen_topic(fake_llm):
    fake_llm.json["evaluation"] = evaluation(1, "weak", None)
    session = new_session()
    filters = Filters(plan="topics", topics=["Ethics & Values", "Health", "Not a topic"], question_mode="real")
    first = session.next_question(filters)
    nxt = session.answer("Not sure.", "coach", filters)["next"]
    assert (first["topic"], nxt["topic"]) == ("Ethics & Values", "Health")


def test_asking_again_skips_the_open_question(fake_llm):
    session = new_session()
    filters = Filters(plan="topics", topics=ETHICS, question_mode="real")
    session.next_question(filters)
    session.next_question(filters)
    first, second = session.turns
    assert first["evaluation"] == {"skipped": True} and session.pending()["id"] == second["id"]


def test_answer_without_an_open_question():
    session = new_session()
    with pytest.raises(InterviewError, match="no open question"):
        session.answer("x", "coach", Filters(plan="topics", topics=ETHICS))


def test_topic_and_daf_requirements():
    session = new_session()
    with pytest.raises(InterviewError, match="Pick at least one topic"):
        session.next_question(Filters(plan="topics", topics=["Nope"]))
    with pytest.raises(InterviewError, match="Add your DAF"):
        session.next_question(Filters(plan="topics", topics=["DAF & Background"], daf="  "))


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
    session.answer("Rates stay to curb inflation.", "coach", Filters(plan="topics", topics=["Economy"]))
    prompt = fake_llm.calls[0]["messages"][0]["content"]
    assert "News item (World, 2026-10-12): RBI holds rates. Repo unchanged." in prompt
    assert "Candidate: Rates stay to curb inflation." in prompt


def test_context_and_reference_sentences():
    assert "real question asked in a past interview (CSE 2024, B board)" in _context(
        {"type": "past", "cse_year": 2024, "board": "B"})
    assert "builds on: DAF" in _context({"type": "generated", "based_on": "DAF"})
    assert _context({"type": "followup"}) == "This is a follow-up question."
    assert _reference([{"source": {"type": "past"}}]) == ""


# ---------- full interview ----------

def test_a_full_interview_runs_to_its_length_with_the_board_choosing(fake_llm):
    fake_llm.json["question"] = written(angle="topic", daf_item=None)
    session = new_session()
    filters = Filters(topics=[], daf=DAF, length=10)
    asked = [session.next_question(filters) for _ in range(10)]
    assert [t["main_index"] for t in asked] == list(range(1, 11))
    assert [t["source"]["asked_by"] for t in asked[:2]] == ["Chairperson"] * 2 and asked[0]["topic"] == "DAF & Background"
    assert asked[-1]["source"]["asked_by"] == "Chairperson"
    assert {t["source"]["asked_by"] for t in asked[2:-1]} == {"Member 1", "Member 2", "Member 3", "Member 4"}

    fake_llm.json["evaluation"] = evaluation()             # good: the member who asked follows up
    follow_up = session.answer("An answer.", "exam", filters)["next"]
    assert follow_up["depth"] == 1 and follow_up["source"] == {"type": "followup", "asked_by": "Chairperson"}
    fake_llm.json["evaluation"] = evaluation(2, "weak", None)
    assert session.answer("Not sure.", "exam", filters)["next"] is None   # the last question: the interview is over
    assert session.next_question(filters) is None
    assert session.next_question(Filters(topics=[], daf=DAF, length=20))["main_index"] == 11   # longer: it goes on


def test_topic_practice_has_no_board_seats(fake_llm):
    t = new_session().next_question(Filters(plan="topics", topics=ETHICS, question_mode="real"))
    assert "asked_by" not in t["source"]


# ---------- not keeping the candidate waiting ----------

def decision(score=4, follow_up="And if your senior insisted?"):
    return lambda messages: {"scores": {k: score for k in evaluator.SCORE_KEYS}, "follow_up_question": follow_up}


@pytest.fixture
def pool():
    return DeferredExecutor()


def background_session(pool):
    return InterviewSession.open(None, get_interviews(), get_bank(), get_question_sources(), BackgroundWork(pool))


def names(fake_llm):
    return [c["name"] for c in fake_llm.calls]


def test_a_full_interview_starts_at_once_and_the_next_question_is_written_meanwhile(fake_llm, pool):
    fake_llm.json["question"] = written(question="A written question?", angle="topic", daf_item=None)
    session = background_session(pool)
    filters = Filters(topics=[], daf=DAF, length=10)
    first = session.next_question(filters)
    assert names(fake_llm) == [] and first["question"] in OPENERS    # no model call to begin
    assert first["source"] == {"type": "opening", "asked_by": "Chairperson"} and first["topic"] == "DAF & Background"
    pool.run()                                                       # writes question 2 in the background
    assert names(fake_llm) == ["question"]
    second = session.next_question(filters)                          # handed over, no waiting for the model
    assert names(fake_llm) == ["question"] and second["question"] == "A written question?"
    assert second["main_index"] == 2 and second["source"]["asked_by"] == "Chairperson"
    assert len(pool.queue) == 1


def test_a_ready_made_question_is_asked_when_the_written_one_is_not_ready(fake_llm, pool, monkeypatch):
    monkeypatch.setattr(session_module, "PREPARED_WAIT", 0.01)
    fake_llm.json["question"] = written(angle="topic", daf_item=None)
    session = background_session(pool)
    filters = Filters(topics=[], length=10)
    session.next_question(filters)                                   # question 2 is queued, not written
    second = session.next_question(filters)
    assert names(fake_llm) == [] and second["main_index"] == 2       # didn't wait: no model call was needed
    assert second["source"]["type"] == "past"


def test_ready_made_questions_fall_back_to_writing_only_when_there_are_none(fake_llm, pool, monkeypatch):
    fake_llm.json["question"] = written(question="Written after all?", angle="topic", daf_item=None)
    sources = {**get_question_sources(), "instant": RealQuestionSource(type("Empty", (), {"similar": lambda self, *a, **k: []})())}
    session = InterviewSession.open(None, get_interviews(), get_bank(), sources, BackgroundWork(pool))
    assert session.next_question(Filters(plan="topics", topics=ETHICS))["question"] == "Written after all?"
    with pytest.raises(InterviewError, match="Add your DAF"):        # still explains what the candidate must do
        session.next_question(Filters(plan="topics", topics=["DAF & Background"]))


def test_topic_practice_starts_with_a_clean_real_question(fake_llm, pool):
    session = background_session(pool)
    sources = dict(session.sources)
    sources["instant"] = type("Fixed", (), {"next": lambda self, ctx: ("A clean question?", {"type": "past"})})()
    session.sources = sources
    fake_llm.json["question"] = written(angle="topic", daf_item=None)
    first = session.next_question(Filters(plan="topics", topics=ETHICS))
    assert first["question"] == "A clean question?" and names(fake_llm) == []


def test_an_opening_question_is_evaluated_as_one(fake_llm):
    assert _context({"type": "opening"}) == "This is the board's opening question."


@pytest.mark.parametrize("text, clean", [
    ("What are the challenges in the criminal justice system?", True),
    ("Is Live-in registration in line with Constitutional rights?", True),
    ("What do you think about MSP legalization?", True),
    ("What qualities do you think is most important? I told about integrity.", False),   # the candidate's note
    ("Have you read any contemporary poets? (I mentioned Rupi Kaur)", False),
    ("What is its severity in the region?", False),                                      # needs the question before
    ("Global economic order kaise change ho raha hai?", False),                          # reads badly in English
    ("Why XX company after your MBA degree?", False),                                    # another candidate's details
    ("How did you come across your hobby of chess?", False),
    ("Some questions about books and reading habits", False),
    ("8 So if someone stays in Mumbai is he a citizen?", False),
    ("Why is it?", False),
])
def test_only_clean_questions_are_asked_in_place_of_a_written_one(sql, text, clean):
    rows = sql(f"SELECT 1 AS ok FROM (VALUES (%s)) AS q(text) WHERE {CLEAN}", (text,))
    assert bool(rows) is clean


def test_a_follow_up_keeps_the_prepared_question_for_its_turn(fake_llm, pool):
    fake_llm.json["question"] = written(question="The prepared one?", angle="topic", daf_item=None)
    fake_llm.json["evaluation"] = evaluation()
    session = background_session(pool)
    filters = Filters(plan="topics", topics=ETHICS)
    session.next_question(filters)
    pool.run()
    assert session.answer("An answer.", "coach", filters)["next"]["depth"] == 1
    assert names(fake_llm).count("question") == 1                    # nothing written for the follow-up
    fake_llm.json["evaluation"] = evaluation(2, "weak", None)
    nxt = session.answer("Not sure.", "coach", filters)["next"]
    assert (nxt["main_index"], nxt["depth"], nxt["question"]) == (2, 0, "The prepared one?")
    assert names(fake_llm).count("question") == 1


def test_nothing_is_prepared_past_the_end_or_for_real_questions(fake_llm, pool):
    fake_llm.json["question"] = written(angle="topic", daf_item=None)
    session = background_session(pool)
    session.repo.add_turn(session.id, 9, 0, "Economy", "Question nine?", {"type": "generated"})
    session.next_question(Filters(topics=[], length=10))             # the last one
    assert not pool.queue
    other = background_session(pool)
    other.next_question(Filters(plan="topics", topics=ETHICS, question_mode="real"))
    assert not pool.queue and session.next_question(Filters(topics=[], length=10)) is None


def test_a_failed_preparation_does_not_stop_the_interview(fake_llm, pool):
    fake_llm.json["question"] = written(angle="topic", daf_item=None)
    session = background_session(pool)
    filters = Filters(topics=[], length=10)
    session.next_question(filters)
    fake_llm.error = RuntimeError("model down")
    pool.run()
    fake_llm.error = None
    assert session.next_question(filters)["main_index"] == 2


def test_exam_mode_waits_only_for_the_decision_and_the_report_waits_for_the_critique(fake_llm, pool):
    fake_llm.json["decision"] = decision()
    fake_llm.json["evaluation"] = evaluation(follow_up="Ignored?")
    session = background_session(pool)
    filters = Filters(plan="topics", topics=ETHICS, question_mode="real")
    first = session.next_question(filters)

    r = session.answer("Rates stay to curb inflation.", "exam", filters, spoken=True)
    assert names(fake_llm) == ["decision"]                           # no critique yet
    assert fake_llm.calls[0]["model"] == "model_4"
    assert "speech recognition" in fake_llm.calls[0]["messages"][0]["content"]
    assert r["evaluation"] == {"pending": True, "spoken": True}
    assert (r["next"]["depth"], r["next"]["question"]) == (1, "And if your senior insisted?")
    assert session.turns[0]["answer"] == "Rates stay to curb inflation."
    report = session.report()
    assert (report["pending"], report["answered"]) == (1, 0)
    assert len(pool.queue) == 1                                      # asking again doesn't start it twice

    pool.run()
    assert names(fake_llm) == ["decision", "evaluation"] and fake_llm.calls[1]["model"] == "model_3"
    prompt = fake_llm.calls[1]["messages"][0]["content"]
    assert "speech recognition" in prompt and "set `follow_up_question` to null" in prompt
    report = session.report()
    assert (report["pending"], report["answered"], report["failed"]) == (0, 1, 0)
    assert report["turns"][0]["id"] == first["id"] and report["turns"][0]["evaluation"]["verdict"] == "good"


def test_exam_mode_follow_ups_obey_the_same_rule(fake_llm, pool):
    fake_llm.json["evaluation"] = evaluation()
    session = background_session(pool)
    filters = Filters(plan="topics", topics=ETHICS, question_mode="real")
    session.next_question(filters)
    fake_llm.json["decision"] = decision(3, "A follow-up the scores don't earn?")     # average 3: below 3.5
    assert session.answer("An answer.", "exam", filters)["next"]["depth"] == 0
    fake_llm.json["decision"] = decision(4, "  Why?  ")
    assert session.answer("An answer.", "exam", filters)["next"]["question"] == "Why?"
    assert session.answer("An answer.", "exam", filters)["next"]["depth"] == 2

    fake_llm.calls.clear()                                           # two follow-ups asked: no decision to make
    assert session.answer("An answer.", "exam", filters)["next"]["depth"] == 0
    assert names(fake_llm) == []

    fake_llm.calls.clear()
    pool.run()
    critique = fake_llm.calls[-1]["messages"][0]["content"]          # the last answer: its whole chain, nothing later
    assert critique.count("Candidate: An answer.") == 3


def test_with_real_threads_the_answer_returns_while_the_critique_is_still_being_written(fake_llm):
    release = threading.Event()

    def slow_critique(messages):
        assert release.wait(10)
        return evaluation()(messages)
    fake_llm.json["decision"] = decision(2, None)
    fake_llm.json["evaluation"] = slow_critique
    session = InterviewSession.open(None, get_interviews(), get_bank(), get_question_sources(), BackgroundWork(workers=1))
    filters = Filters(plan="topics", topics=ETHICS, question_mode="real")
    session.next_question(filters)
    assert session.answer("An answer.", "exam", filters)["next"]["main_index"] == 2   # returned, critique still blocked
    assert session.report()["pending"] == 1
    release.set()
    for _ in range(100):
        if not session.report()["pending"]:
            break
        time.sleep(0.05)
    assert session.report()["answered"] == 1


def test_markdown_emphasis_never_reaches_the_candidate(fake_llm):
    def emphatic(messages):
        return {"scores": {k: 4 for k in evaluator.SCORE_KEYS}, "verdict": "good", "strengths": ["A *clear* structure throughout"],
                "issues": [{"quote": None, "type": "vague", "why": "The board asked what in *you* matters here", "fix": "say **this**"}],
                "critique": "You missed *you*.", "missing_points": ["A sense of *depth* on the subject"],
                "model_answer_points": ["**Start** with the constitutional position"],
                "follow_up_question": "And *why*?"}
    fake_llm.json["evaluation"] = emphatic
    session = new_session()
    filters = Filters(plan="topics", topics=ETHICS, question_mode="real")
    session.next_question(filters)
    r = session.answer("An answer.", "coach", filters)
    e = r["evaluation"]
    assert e["critique"] == "You missed you." and e["strengths"] == ["A clear structure throughout"]
    assert e["missing_points"] == ["A sense of depth on the subject"]
    assert e["model_answer_points"] == ["Start with the constitutional position"]
    assert (e["issues"][0]["why"], e["issues"][0]["fix"]) == ("The board asked what in you matters here", "say this")
    assert r["next"]["question"] == "And why?"

    fake_llm.json["decision"] = decision(4, "And *how*?")
    assert evaluator.decide_follow_up("Ethics & Values", "ctx", "", "Board: q\nCandidate: a", 1, []) == "And how?"
    fake_llm.json["question"] = written(question="What about *this*?", angle="topic", daf_item=None)
    assert new_session().next_question(Filters(plan="topics", topics=ETHICS))["question"] == "What about this?"


def test_a_background_evaluation_retries_then_gives_up_so_the_report_can_finish(fake_llm, pool, monkeypatch):
    monkeypatch.setattr(session_module, "RETRY_DELAYS", (0, 0))
    fake_llm.json["decision"] = decision(2, None)
    session = background_session(pool)
    filters = Filters(plan="topics", topics=ETHICS, question_mode="real")
    session.next_question(filters)
    session.answer("One.", "exam", filters)
    session.answer("Two.", "exam", filters)

    attempts = []

    def flaky(messages):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("rate limited")
        return evaluation()(messages)
    fake_llm.json["evaluation"] = flaky
    pool.queue[1:] = []                                              # the second answer is handled below
    pool.run()
    assert len(attempts) == 2 and session.turns[0]["evaluation"]["verdict"] == "good"

    def down(messages):
        attempts.append(1)
        raise RuntimeError("down")
    fake_llm.json["evaluation"] = down
    attempts.clear()
    session.background = BackgroundWork(pool)                        # a restart lost it: the report starts it again
    assert session.report()["pending"] == 1
    pool.run()
    assert len(attempts) == 3
    report = session.report()
    assert (report["pending"], report["failed"], report["answered"]) == (0, 1, 1)

    fake_llm.calls.clear()
    session.finish_evaluation(session.turns[1]["id"])                # no longer pending: nothing to do
    assert fake_llm.calls == []


# ---------- report ----------

def test_report_averages_by_dimension_and_topic(fake_llm):
    session = new_session()
    filters = Filters(plan="topics", topics=["Ethics & Values", "Health"], question_mode="real")
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
