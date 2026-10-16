"""Edge cases of segmentation, structure and classification not covered by the synthetic export."""

from datetime import datetime

from app.ingest.parse import _text
from app.ingest.segment import build_units
from app.ingest.structure import structure
from app.ingest.transcripts import board_of, chunks, classify, metadata
from app.interview.evaluator import _quote_in, guard

QUESTIONS = "\n".join(f"Q{i}. What is question number {i} about governance?" for i in range(1, 8))


def test_member_labels_in_every_form():
    text = ("Header line\nChairman: So you are from Kota?\nWhat next?\n"
            "Lady member\nWhy?\nSecond member\nHow?\nM-3\nWhen?\n"
            "Member 4 (sir)\nI said it was a good question\n- \n• What is the plan?\n")
    sections = structure(text)["sections"]
    members = [s["member"] for s in sections]
    assert members == ["Chairperson", "Lady member", "Member 2", "Member 3", "Member 4"]
    assert sections[0]["items"][0]["text"].startswith("So you are from Kota")
    assert sections[4]["items"][0]["kind"] == "note" and sections[4]["gender"] == "male"


def test_structure_without_member_labels():
    outline = structure("Name - A\nBoard - X\n\n1. What is federalism?\nWhy does it matter?")
    assert [s["title"] for s in outline["sections"]] == ["Questions"] and len(outline["sections"][0]["items"]) == 2
    assert structure("Just a note without questions")["sections"] == []


def test_classify_reasons():
    assert classify({"text": "short"}) == "too short"
    assert classify({"text": "word " * 200}) == "no questions or member sections"
    assert classify({"text": "Some intro\n" + QUESTIONS * 2}) == "no transcript header"
    two = ("Name - A\nBoard - Sanjay Verma\nDate - 1 Jan\n" + QUESTIONS + "\n") * 2
    assert classify({"text": two}) == "may contain more than one transcript"


def test_unknown_board_ifos_and_anonymous_alias():
    meta = metadata({"text": "Name - ***\nIFoS interview\nBoard - someone new\nComputer Science optional\n" + QUESTIONS
                     + "\nInterview marks: 999\nPT score 160", "posted_at": "2025-03-01T10:00:00"})
    assert meta["board"] == "Unknown" and meta["exam"] == "IFoS" and meta["alias"] is None
    assert meta["optional_subject"] == "Computer Science" and meta["pt_marks"] == 160
    assert board_of("nothing here") == "Unknown"


def test_long_sections_are_capped():
    text = "Chairman\n" + "\n".join(f"Question {i} about a fairly long topic of public policy?" for i in range(80))
    parts = chunks(text)
    assert len(parts) > 1 and all(len(p["text"]) <= 1700 for p in parts) and parts[0]["section"] == "Chairman"
    assert chunks("plain text only")[0]["section"] == "text"


def test_short_headerless_message_is_noise():
    units, noise = build_units([{"id": 1, "posted_at": "2025-01-01T10:00:00", "forwarded_from": None,
                                 "reactions": 0, "text": "Best of luck everyone!"}])
    assert units == [] and noise[0]["reason"] == "short"


def test_parse_text_of_missing_div():
    assert _text(None) == ""


def test_quote_matching_and_guard():
    assert not _quote_in("", "answer")
    assert _quote_in("the farm laws were good", "I think the farm laws were really good overall")
    ev = {"issues": [{"quote": "invented words here", "type": "factual_error", "why": "x" * 30, "fix": "f"},
                     {"quote": None, "type": "vague", "why": "short", "fix": "f"}],
          "critique": f"In {datetime.now().year - 1} it rose 12%.", "strengths": [], "missing_points": [],
          "model_answer_points": []}
    out = guard(ev, "my answer", allowed="my answer")
    # a factual error quoting words that aren't in the answer is dropped; so is an issue with a too-short why
    assert out["issues"] == [] and out["guard"]["issues"] == 2
    assert "12%" not in out["critique"]
