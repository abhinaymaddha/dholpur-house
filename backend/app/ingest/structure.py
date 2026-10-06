"""Turn a free-form transcript into a readable outline for the reader view.

    {"header":   [{"key": "Board", "value": "Sanjay Verma sir"}, {"text": "First to go"}],
     "sections": [{"title": "Chairman", "member": "Chairperson", "gender": "male",
                   "items": [{"kind": "q", "text": "Why civil services?"}, {"kind": "note", "text": "I said ..."}]}]}

Best effort and lossless: every non-empty line of the original ends up somewhere, so the reader can
always fall back to "Original text" when a candidate's format defeats the heuristics.
"""

from __future__ import annotations

import re

from .transcripts import SECTION

# Sections that aren't a board member: mocks, acknowledgements, tips, observations.
NOTES_SECTION = re.compile(
    r"(?im)^\s*[-*•#>\[\] ]*(?:mocks?\b|o2o|daf discussion|acknowledg\w*|thanks to|thank you all|gratitude|"
    r"observations?|experience|overall experience|tips?\b|takeaways?|key learnings?|pt marks|my marks|"
    r"result\b|conclusion|relevance of mock|utility of mock)[^\n]{0,80}$")
KEY_VALUE = re.compile(r"^\s*[*_]*([A-Za-z][A-Za-z .&/()']{1,28}?)[*_]*\s*(?:[:\-–~—>]+|=)\s*(.+)$")
LIST_PREFIX = re.compile(r"^\s*(?:[-*•▪◦→>]+|(?:Q\.?\s*)?\d{1,2}\s*[.):\-]|Q\.?\s*[-:.)]|Q\s+)\s*", re.I)
LABEL = re.compile(r"(?i)^\s*[-*•#>\[\] ]*(chair(?:man|person|woman)?|member\s*[-–]?\s*\d|m\s?[-–]?\s?\d|lady\s*member|"
                   r"(?:1st|2nd|3rd|4th|first|second|third|fourth)\s*member)\b")
# Lines that report the candidate's answer or narration rather than a question.
ANSWER = re.compile(r"(?i)^\s*(?:i\s+(?:said|told|answered|replied|mentioned|explained|spoke|gave|started|was|didn|don|could|think)|"
                    r"i'm|i've|me\s*[:\-–]|ans(?:wer)?\s*[:\-–.]|a\s*[:\-–]\s|my (?:answer|reply)|replied|->|=>|→|"
                    r"\*+\s*(?:sir|ma'?am|yes|no|thank|i\b)|\(\s*i\b|answered)")
FEMALE = re.compile(r"(?i)\b(lady|female|woman|ma'?am|madam|mam|she)\b")
MALE = re.compile(r"(?i)\b(male|sir|gentleman|he)\b")
ORDINAL = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4}


def _member(label: str) -> str:
    low = label.lower()
    if low.startswith("chair"):
        return "Chairperson"
    if "lady" in low:
        return "Lady member"
    digit = re.search(r"\d", low)
    if digit:
        return f"Member {digit.group()}"
    for word, n in ORDINAL.items():
        if low.startswith(word):
            return f"Member {n}"
    return label.title()


def _gender(title: str, member: str) -> str:
    if member == "Lady member" or FEMALE.search(title):
        return "female"
    return "male" if MALE.search(title) else "unknown"


def _items(lines: list[str], questions: bool = True) -> list[dict]:
    """Inside a member section a line is a question unless it reads like an answer or narration."""
    items = []
    for line in lines:
        if not line.strip():
            continue
        answer = bool(ANSWER.match(line))
        text = LIST_PREFIX.sub("", line).strip() if LIST_PREFIX.match(line) and not answer else line.strip()
        if not text:
            continue
        items.append({"kind": "q" if questions and not answer else "note", "text": text})
    return items


def _line_starts(rx: re.Pattern, text: str) -> set[int]:
    """Match positions moved past leading whitespace (the patterns' ^\\s* also eats blank lines)."""
    return {m.start() + len(m.group()) - len(m.group().lstrip()) for m in rx.finditer(text)}


def structure(text: str) -> dict:
    starts = sorted(_line_starts(SECTION, text) | _line_starts(NOTES_SECTION, text))
    if not starts:
        # No member labels: header is the lines before the first question-like line.
        lines = text.splitlines()
        first_q = next((i for i, ln in enumerate(lines) if LIST_PREFIX.match(ln) or ln.rstrip().endswith("?")), len(lines))
        head, body = lines[:first_q], lines[first_q:]
        sections = [{"title": "Questions", "member": None, "gender": "unknown", "items": _items(body)}] if body else []
    else:
        head = text[: starts[0]].splitlines()
        sections = []
        for a, b in zip(starts, starts[1:] + [len(text)]):
            block = text[a:b].splitlines()
            title_line = block[0].strip()
            rest = block[1:]
            m = LABEL.match(title_line)
            if m:
                member = _member(m.group(1))
                remainder = title_line[m.end():].strip(" *_-–:)(.")
                # "Chairman: So you are from Kota?" -> the question rides on the label line
                if remainder.endswith("?") or len(remainder) > 40:
                    rest = [remainder] + rest
                    title_line = m.group(0).strip(" *_-#:>[]")
                sections.append({"title": title_line.strip(" *_-#:>[]"), "member": member,
                                 "gender": _gender(title_line, member), "items": _items(rest)})
            else:
                kv = KEY_VALUE.match(title_line)
                title, first = (kv.group(1), kv.group(2)) if kv else (title_line.strip(" *_-#:>[]"), None)
                sections.append({"title": title.strip(), "member": None, "gender": "unknown",
                                 "items": _items(([first] if first else []) + rest, questions=False)})

    header = []
    for line in head:
        if not line.strip():
            continue
        kv = KEY_VALUE.match(line)
        header.append({"key": kv.group(1).strip(), "value": kv.group(2).strip()} if kv else {"text": line.strip()})
    return {"header": header, "sections": [s for s in sections if s["items"] or s["member"]]}


def question_count(outline: dict) -> int:
    return sum(i["kind"] == "q" for s in outline["sections"] if s["member"] or s["title"] == "Questions"
               for i in s["items"])
