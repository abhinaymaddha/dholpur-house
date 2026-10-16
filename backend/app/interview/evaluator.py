"""Critical evaluation of one answer (model_3), with guards against invented facts.

The prompt (prompts/evaluate.md) asks for harsh but specific feedback: every issue quotes the
candidate's own words and says why it is a problem. Two guards then run in code, because a model
can be told not to invent facts but can't be trusted to comply:

- quote check: an issue's quote must actually appear in the answer; a factual-error issue whose
  quote can't be found is dropped (we can't show the candidate where they went wrong);
- specifics check: recent years, percentages and money figures that appear nowhere in the question,
  the answer, the exchange or the reference facts are removed (sentence or list item), since those
  are exactly the "June 2026 interim deal" style fabrications. Older years (history, statutes like
  "Disaster Management Act, 2005") are stable knowledge and are left alone.
"""

from __future__ import annotations

import re
from datetime import date

from app.interview import prompts
from app.services.llm import complete_json

MODEL = "model_3"
SCORE_KEYS = ["relevance", "accuracy", "depth", "balance", "practicality", "clarity", "tone"]
ISSUE_TYPES = ["factual_error", "unsupported_claim", "vague", "off_topic", "missing_perspective",
               "impractical", "tone", "structure"]


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


SCHEMA = _obj({
    "scores": _obj({k: {"type": "integer"} for k in SCORE_KEYS}),
    "verdict": {"type": "string", "enum": ["good", "partial", "weak"]},
    "issues": {"type": "array", "items": _obj({
        "quote": {"type": ["string", "null"]},
        "type": {"type": "string", "enum": ISSUE_TYPES},
        "why": {"type": "string"},
        "fix": {"type": "string"},
    })},
    "strengths": {"type": "array", "items": {"type": "string"}},
    "critique": {"type": "string"},
    "missing_points": {"type": "array", "items": {"type": "string"}},
    "model_answer_points": {"type": "array", "items": {"type": "string"}},
    "follow_up_question": {"type": ["string", "null"]},
})

# Specifics a model tends to invent. Kept only if the same text appears in the allowed sources.
RECENT_YEARS = 10   # years from (this year - RECENT_YEARS) on count as "recent" and need a source
_SPECIFIC = re.compile(
    r"(?<!Act, )(?<!Act )\b20\d{2}\b"                               # years (filtered to recent ones below)
    r"|\b\d+(?:\.\d+)?\s?(?:%|per\s?cent)"                          # percentages
    r"|(?:₹|rs\.?|inr|\$|usd)\s?\d[\d,.]*"                          # money with a currency
    r"|\b\d[\d,.]*\s?(?:crore|lakh|billion|million|trillion|bn)\b",  # big amounts
    re.I)
# Sentence breaks, but not after abbreviations like "e.g.", "i.e.", "Sec.", "No.", "Art.", "vs."
_SENTENCE = re.compile(r"(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bSec\.)(?<!\bNo\.)(?<!\bArt\.)(?<!\bvs\.)(?<=[.!?])\s+(?=[A-Z\"'(])")
_NO_QUOTE = {"", "none", "null", "n/a", "na", "-"}
_MIN_WHY = 25   # an issue whose explanation was cut below this is no longer useful


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[“”\"'’‘`]", "", text.lower())).strip(" .,;:-")


def _quote_in(quote: str, answer: str) -> bool:
    q, a = _norm(quote), _norm(answer)
    if not q:
        return False
    if q in a:
        return True
    words = q.split()   # tolerate small paraphrase: most of the quote's words, in the answer
    return len(words) >= 3 and sum(w in a.split() for w in words) / len(words) >= 0.8


def _unsupported(text: str, allowed: str) -> bool:
    first_recent = date.today().year - RECENT_YEARS
    for m in _SPECIFIC.finditer(text):
        token = m.group(0)
        if token.isdigit() and int(token) < first_recent:
            continue   # an older year: history or a statute, stable knowledge
        if token.lower() not in allowed:
            return True
    return False


def _clean_text(text: str, allowed: str) -> tuple[str, int]:
    kept, removed = [], 0
    for sentence in _SENTENCE.split(text):
        if _unsupported(sentence, allowed):
            removed += 1
        else:
            kept.append(sentence)
    return " ".join(kept), removed


def guard(evaluation: dict, answer: str, allowed: str) -> dict:
    """Apply the quote and specifics checks. Records what was removed under evaluation['guard']."""
    allowed = allowed.lower()
    removed = {"quotes": 0, "issues": 0, "specifics": 0}

    issues = []
    for issue in evaluation.get("issues", []):
        if (issue.get("quote") or "").strip().lower() in _NO_QUOTE:
            issue["quote"] = None
        if issue.get("quote") and not _quote_in(issue["quote"], answer):
            if issue["type"] == "factual_error":
                removed["issues"] += 1
                continue
            issue["quote"] = None
            removed["quotes"] += 1
        for field in ("why", "fix"):
            issue[field], n = _clean_text(issue[field], allowed)
            removed["specifics"] += n
        if len(issue["why"].strip()) >= _MIN_WHY:
            issues.append(issue)
        else:
            removed["issues"] += 1
    evaluation["issues"] = issues

    evaluation["critique"], n = _clean_text(evaluation.get("critique", ""), allowed)
    removed["specifics"] += n
    for field in ("missing_points", "model_answer_points", "strengths"):
        items = evaluation.get(field, [])
        # drop invented specifics and junk fragments (a model sometimes echoes a field name)
        kept = [i for i in items if len(i.strip()) >= 12 and "_" not in i.strip() and not _unsupported(i, allowed)]
        removed["specifics"] += len(items) - len(kept)
        evaluation[field] = kept
    evaluation["guard"] = removed
    return evaluation


def score(evaluation: dict) -> dict:
    """Clamp scores and enforce the rubric: 'good' needs every score >= 3 and an average >= 3.5."""
    scores = {k: max(1, min(5, int(evaluation["scores"].get(k, 1)))) for k in SCORE_KEYS}
    evaluation["scores"] = scores
    evaluation["average"] = round(sum(scores.values()) / len(scores), 2)
    if evaluation["verdict"] == "good" and (min(scores.values()) < 3 or evaluation["average"] < 3.5):
        evaluation["verdict"] = "partial"
    return evaluation


def evaluate(topic_name: str, context: str, reference: str, exchange: str, answer: str,
             followups_left: int, followup_pairs: list[tuple[str, str]]) -> tuple[dict, str | None]:
    """Evaluate the latest answer. Returns (evaluation, follow-up question or None)."""
    topic = prompts.topic(topic_name)
    instruction = (
        "If (and only if) the verdict is good, write one follow-up question in `follow_up_question` that probes "
        "the candidate's judgement on this answer: challenge a specific claim they made, push back with a "
        "counter-view, or ask what they would do if a condition changed. Do not ask them to cite dates, statistics "
        "or specific news. One short question, no preamble. Otherwise set it to null. "
        f"(Follow-ups left for this question: {followups_left}.)"
        if followups_left > 0 else "No more follow-ups for this question: set `follow_up_question` to null.")
    prompt = prompts.render(
        "evaluate", topic=topic.name, guidance=topic.guidance, today=date.today().strftime("%d %B %Y"),
        context=context, reference=reference or "(none: judge facts only against stable, well-established knowledge)",
        exchange=exchange,
        followup_examples="\n".join(f"- Q: {q}\n  Follow-up: {f}" for q, f in followup_pairs) or "- (none found)",
        followup_instruction=instruction)
    evaluation = complete_json(MODEL, [{"role": "user", "content": prompt}], SCHEMA, "evaluation")
    follow_up = evaluation.pop("follow_up_question", None)
    evaluation = score(guard(evaluation, answer, allowed=f"{exchange}\n{reference}"))
    return evaluation, (follow_up.strip() if follow_up else None)
