import pytest

from app.interview import prompts


def test_every_topic_parses_with_guidance():
    topics = prompts.topics()
    assert len(topics) >= 15 and topics["Economy"].news and topics["DAF & Background"].needs_daf
    assert all(t.testing for t in topics.values())


def test_render_requires_every_placeholder():
    with pytest.raises(KeyError, match="evaluate.md needs"):
        prompts.render("evaluate", topic="x")


def test_unknown_topic():
    with pytest.raises(KeyError, match="Unknown topic"):
        prompts.topic("Astrology")


def test_topic_file_without_header(tmp_path, monkeypatch):
    (tmp_path / "topics").mkdir()
    (tmp_path / "topics" / "plain.md").write_text("Just guidance.")
    monkeypatch.setattr(prompts, "PROMPTS_DIR", tmp_path)
    t = prompts.topic("plain")
    assert (t.news, t.needs_daf, t.guidance, t.testing) == (False, False, "Just guidance.", "Just guidance.")


@pytest.mark.parametrize("text, expected", [
    ("what in *you* makes you eligible", "what in you makes you eligible"),
    ("a **bold** and ***very bold*** claim", "a bold and very bold claim"),
    ("*one* and *two*", "one and two"),
    ("2 * 3 is six", "2 * 3 is six"),
    ("nothing to change", "nothing to change"),
])
def test_plain_removes_emphasis_only(text, expected):
    assert prompts.plain(text) == expected


def test_the_decision_prompt_refuses_credit_for_generic_answers():
    text = (prompts.PROMPTS_DIR / "decide.md").read_text()
    assert "could be pasted under a different question" in text
