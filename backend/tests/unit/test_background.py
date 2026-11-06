"""Background work: prepared questions and evaluations."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

from app.interview.background import BackgroundWork
from tests.fixtures.fakes import DeferredExecutor


def test_a_prepared_question_is_handed_over_once_and_only_for_the_same_choices():
    pool = DeferredExecutor()
    work, sid = BackgroundWork(pool), uuid4()
    calls = []
    work.prepare(sid, ("a",), lambda: calls.append("a") or "first")
    work.prepare(sid, ("a",), lambda: calls.append("again") or "duplicate")     # already being prepared
    pool.run()
    assert calls == ["a"] and work.take(sid, ("a",)) == "first"
    assert work.take(sid, ("a",)) is None

    work.prepare(sid, ("b",), lambda: "stale")
    pool.run()
    assert work.take(sid, ("changed",)) is None and work.take(sid, ("b",)) is None   # a mismatch discards it


def test_a_failed_preparation_means_write_it_now():
    pool = DeferredExecutor()
    work, sid = BackgroundWork(pool), uuid4()

    def fail():
        raise RuntimeError("model down")
    work.prepare(sid, ("a",), fail)
    pool.run()
    assert work.take(sid, ("a",)) is None


def test_take_waits_for_a_question_still_being_written():
    started, release = Event(), Event()

    def write():
        started.set()
        release.wait(5)
        return "written"
    with ThreadPoolExecutor(1) as pool:
        work, sid = BackgroundWork(pool), uuid4()
        work.prepare(sid, ("a",), write)
        started.wait(5)
        release.set()
        assert work.take(sid, ("a",)) == "written"


def test_take_gives_up_after_waiting():
    release = Event()
    with ThreadPoolExecutor(1) as pool:
        work, sid = BackgroundWork(pool), uuid4()
        work.prepare(sid, ("a",), lambda: release.wait(5))
        assert work.take(sid, ("a",), wait=0.01) is None
        release.set()
        assert work.take(sid, ("a",)) is None                       # dropped, not handed over later


def test_abandoned_preparations_are_dropped_oldest_first():
    pool = DeferredExecutor()
    work = BackgroundWork(pool, keep=2)
    a, b, c = uuid4(), uuid4(), uuid4()
    for sid in (a, b, c):
        work.prepare(sid, ("k",), lambda: "q")
    pool.run()
    assert work.take(a, ("k",)) is None and work.take(c, ("k",)) == "q"


def test_an_evaluation_runs_once_at_a_time_and_a_failure_frees_it():
    pool = DeferredExecutor()
    work = BackgroundWork(pool)
    runs = []

    def fail():
        runs.append(1)
        raise RuntimeError("boom")
    work.evaluate(7, fail)
    work.evaluate(7, fail)
    assert len(pool.queue) == 1
    pool.run()
    assert runs == [1]
    work.evaluate(7, fail)
    pool.run()
    assert runs == [1, 1]
