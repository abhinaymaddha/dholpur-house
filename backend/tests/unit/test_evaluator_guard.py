from app.interview.evaluator import SCORE_KEYS, guard, score

ANSWER = ("Sir, India should keep channels open with both Washington and Tehran. Article 370 deals with the "
          "Emergency, so the Centre can act. We must protect Chabahar and diversify energy imports.")


def evaluation(**kw):
    base = {"scores": {k: 4 for k in SCORE_KEYS}, "verdict": "good", "issues": [], "strengths": [],
            "critique": "", "missing_points": [], "model_answer_points": []}
    return base | kw


def test_issue_with_a_real_quote_is_kept():
    e = guard(evaluation(issues=[{"quote": "Article 370 deals with the Emergency", "type": "factual_error",
                                  "why": "Article 370 was about J&K's special status, not Emergency.", "fix": "Cite Article 352."}]),
              ANSWER, allowed=ANSWER)
    assert len(e["issues"]) == 1 and e["issues"][0]["quote"]


def test_factual_error_with_invented_quote_is_dropped():
    e = guard(evaluation(issues=[{"quote": "India should join NATO", "type": "factual_error", "why": "Wrong.", "fix": "x"}]),
              ANSWER, allowed=ANSWER)
    assert e["issues"] == [] and e["guard"]["issues"] == 1


def test_other_issue_with_invented_quote_keeps_the_point_without_the_quote():
    e = guard(evaluation(issues=[{"quote": "something never said", "type": "vague", "why": "Too general to show any real judgement.", "fix": "Be specific."}]),
              ANSWER, allowed=ANSWER)
    assert e["issues"][0]["quote"] is None and e["guard"]["quotes"] == 1


def test_invented_years_and_figures_are_removed():
    e = guard(evaluation(
        critique="You ignored the June 2026 interim deal. You also missed Iran's view.",
        missing_points=["The 60-day framework agreed in 2026", "Iran's likely reaction"],
        model_answer_points=["Trade fell 12% last year", "Engage all parties"]),
        ANSWER, allowed=ANSWER)
    assert e["critique"] == "You also missed Iran's view."
    assert e["missing_points"] == ["Iran's likely reaction"]
    assert e["model_answer_points"] == ["Engage all parties"]
    assert e["guard"]["specifics"] == 3


def test_figures_from_the_reference_are_allowed():
    reference = "News item: Trump says U.S. will not resume strikes before Nov. 3, 2026 midterms."
    e = guard(evaluation(critique="You did not connect it to the 2026 midterms."), ANSWER, allowed=ANSWER + reference)
    assert e["critique"] == "You did not connect it to the 2026 midterms."


def test_good_needs_every_score_at_least_three():
    e = score(evaluation(scores={k: 5 for k in SCORE_KEYS} | {"tone": 2}))
    assert e["verdict"] == "partial"


def test_statute_years_and_history_are_kept():
    e = guard(evaluation(critique="You did not cite the Disaster Management Act, 2005. Gandhi returned in 1915."),
              ANSWER, allowed=ANSWER)
    assert e["critique"] == "You did not cite the Disaster Management Act, 2005. Gandhi returned in 1915."


def test_abbreviations_do_not_split_sentences():
    e = guard(evaluation(critique="Cite a forum, e.g. SCO. Also missed Iran's view in the 2026 deal."),
              ANSWER, allowed=ANSWER)
    assert e["critique"] == "Cite a forum, e.g. SCO."


def test_placeholder_quotes_become_null():
    e = guard(evaluation(issues=[{"quote": "None", "type": "missing_perspective",
                                  "why": "You never considered Iran's own interests in Chabahar.", "fix": "Add it."}]),
              ANSWER, allowed=ANSWER)
    assert e["issues"][0]["quote"] is None and e["guard"]["quotes"] == 0
