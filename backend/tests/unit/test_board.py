"""The full-interview plan: who asks what, in what order."""

from itertools import groupby

import pytest

from app.interview import prompts
from app.interview.board import CHAIR, CLOSING, DAF, MEMBER_AREAS, plan


@pytest.mark.parametrize("length, opening, shares", [(10, 2, [2, 2, 2, 1]), (20, 4, [4, 4, 4, 3]),
                                                      (30, 6, [6, 6, 6, 5])])
def test_the_chair_opens_and_closes_and_the_members_share_the_middle(length, opening, shares):
    slots = plan(length, "seed", {}, has_daf=True)
    assert len(slots) == length
    assert [s.member for s in slots[:opening]] == [CHAIR] * opening
    assert slots[0].topic == DAF and slots[1].topic == "Motivation & Personal"
    assert slots[-1].member == CHAIR and slots[-1].topic in CLOSING
    middle = [(m, len(list(g))) for m, g in groupby(s.member for s in slots[opening:-1])]
    assert middle == list(zip(MEMBER_AREAS, shares))
    assert all(s.topic in prompts.topics() for s in slots)


def test_members_keep_to_their_areas_and_never_ask_the_same_topic_twice_in_a_row():
    for seed in map(str, range(50)):
        slots = plan(30, seed, {}, has_daf=False)
        for member, group in groupby(slots, key=lambda s: s.member):
            topics = [s.topic for s in group]
            if member != CHAIR:
                assert set(topics) <= set(MEMBER_AREAS[member])
                assert all(a != b for a, b in zip(topics, topics[1:]))


def test_the_daf_is_asked_about_only_when_given():
    assert all(s.topic != DAF for seed in map(str, range(50)) for s in plan(30, seed, {}, has_daf=False))
    assert plan(10, "x", {}, has_daf=False)[0].topic == "Motivation & Personal"
    member_1 = [s.topic for seed in map(str, range(50)) for s in plan(30, seed, {}, has_daf=True) if s.member == "Member 1"]
    assert DAF in member_1


def test_the_plan_is_stable_per_session_and_follows_how_often_boards_ask():
    assert plan(20, "abc", {}, True) == plan(20, "abc", {}, True)
    assert len({tuple(plan(20, str(i), {}, True)) for i in range(10)}) > 1
    heavy = {"Economy": 1000}
    member_2 = [s.topic for seed in map(str, range(100)) for s in plan(30, seed, heavy, False) if s.member == "Member 2"]
    assert member_2.count("Economy") > len(member_2) / 3   # can't be asked twice in a row, so at most half
