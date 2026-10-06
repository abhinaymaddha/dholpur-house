from app.ingest.structure import question_count, structure
from app.ingest.tags import tag_transcript

TRANSCRIPT = """Name: Static
Board: Sanjay Verma sir
DAF: Haryana, IIT BHU, Chemical Engg., Bhagwad Geeta, cricket, PSIR

Chairman
1. Why did you leave IOCL for civil services?
2. What is India's policy towards China and Pakistan?
I said we follow neighbourhood first.

M2 (lady member)
- What is the role of the Governor under the Constitution?
- Should Article 356 be used more often?
Suppose you are DM of a flood-hit district, what will you do?

Mocks: Vajiram, Samkalp
"""


def test_profile_tags_come_from_the_daf():
    tags = tag_transcript(TRANSCRIPT, "Haryana, IIT BHU, Chemical Engg., Bhagwad Geeta, cricket, PSIR", None)
    assert tags["background"] == ["Engineering"]
    assert tags["optional_tag"] == "PSIR"
    assert tags["states"] == ["Haryana"]
    assert tags["interests"] == ["Cricket"]


def test_topics_need_repeated_evidence():
    topics = tag_transcript(TRANSCRIPT, None, None)["topics"]
    assert "International Relations" in topics          # China + Pakistan + neighbourhood
    assert "Polity & Constitution" in topics            # Governor + Constitution + Article 356
    assert "Situational / Hypothetical" in topics       # one "Suppose you" is enough
    assert "Economy" not in topics


def test_ma_am_is_not_a_masters_degree():
    assert "Humanities" not in tag_transcript("Board - Suman ma'am\nDAF - MBBS, Kota", "MBBS, Kota", None)["background"]


def test_structure_outline():
    out = structure(TRANSCRIPT)
    assert out["header"][1] == {"key": "Board", "value": "Sanjay Verma sir"}
    chair, lady, mocks = out["sections"]
    assert chair["member"] == "Chairperson" and [i["kind"] for i in chair["items"]] == ["q", "q", "note"]
    assert chair["items"][0]["text"] == "Why did you leave IOCL for civil services?"
    assert lady["member"] == "Member 2" and lady["gender"] == "female" and len(lady["items"]) == 3
    assert mocks["member"] is None and mocks["items"] == [{"kind": "note", "text": "Vajiram, Samkalp"}]
    assert question_count(out) == 5
