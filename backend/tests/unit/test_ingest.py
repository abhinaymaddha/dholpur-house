from app.ingest.segment import build_units, dedupe
from app.ingest.transcripts import board_of, chunks, classify, metadata

TRANSCRIPT = """Name - Static
Interview- 08/01/2025
Board - Sanjay verma
DAF - Haryana , IIT BHU Varanasi, IOCL , Chemical Engg., Bhagwad Geeta
Opt - math

Chairman
How many web series have u watched?
Best and worst u watched? and why ?
Why you read gita and when u started it ?

M1
What is ur understanding by dharma?
Is ancient society dharma based?

M2 ( female member )
Difference between karma , bhakti and sankhya yoga
Favourite shlok, context and why ?
3 types of guna , 3 types of miseries/sufferings

M3
With economic growth, inequality is rising. Why?
What would you do as DM of a drought-hit district in Haryana?
"""


def msg(i, text, ts="2025-01-15T10:00:00"):
    return {"id": i, "posted_at": ts, "forwarded_from": None, "reactions": 0, "text": text}


def test_continuation_is_stitched_and_new_transcript_is_split():
    part1 = TRANSCRIPT + "x" * (3400 - len(TRANSCRIPT))          # long enough to look cut by Telegram
    msgs = [
        msg(1, part1, "2025-01-15T10:00:00"),
        msg(2, "M3\nWhat is repo rate?\nWhy does RBI use it?", "2025-01-15T10:00:30"),
        msg(3, "Name: Other\nBoard: BB Swain sir\nDate: 9 Jan\nChairman\nWhat is BDO work?", "2025-01-15T10:01:00"),
    ]
    units, _ = build_units(msgs)
    assert [u["message_ids"] for u in units] == [[1, 2], [3]]


def test_reposted_transcript_is_deduped():
    units, _ = build_units([msg(1, TRANSCRIPT, "2025-01-15T10:00:00"),
                            msg(2, TRANSCRIPT + "\nPT marks - 187", "2025-01-20T10:00:00")])
    kept = dedupe(units)
    assert len(kept) == 1 and kept[0]["unit_id"] == "u2" and kept[0]["duplicates"] == ["u1"]


def test_clear_transcript_is_accepted_and_admin_post_held():
    assert classify({"text": TRANSCRIPT}) is None
    request = "Hello people,\nYou are requested to share your interview transcripts of CSPT 2025 " + "." * 700
    assert classify({"text": request}) == "admin request"


def test_metadata():
    meta = metadata({"text": TRANSCRIPT + "\nPT MARKS - 187", "posted_at": "2025-01-15T10:00:00"})
    assert meta["board"] == "Sanjay Verma"
    assert meta["alias"] == "Static"
    assert meta["optional_subject"] == "math"
    assert meta["pt_marks"] == 187
    assert meta["cse_year"] == 2024 and meta["exam"] == "CSE"


def test_board_spellings():
    assert board_of("Board- sheelbardhan sir") == "Sheel Vardhan Singh"
    assert board_of("Board - Sujata ma'am") == "Sujata Chaturvedi"
    assert board_of("Lt. Gen. Raj Shukla sir board") == "Lt Gen Raj Shukla"


def test_chunks_follow_member_sections():
    sections = [c["section"].lower() for c in chunks(TRANSCRIPT)]
    assert sections[0] == "header" and "chairman" in sections and "m1" in sections
