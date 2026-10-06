"""Shortlist clearly marked transcripts, read their headers, and cut them into retrieval chunks.

Everything here is deterministic: no LLM is involved, so ingestion is free and repeatable.
Units that don't look like one clearly marked transcript are put on hold with a reason.
"""
from __future__ import annotations

import re
from datetime import date

from .segment import BOARD_NAME, _header_hits

# Canonical chairperson names, matched against the header area.
BOARDS = [
    ("Sanjay Verma", r"sanjay\s*v[ae]rma|sanjeev\s*verma|\bverma\b"),
    ("Dinesh Dasa", r"dinesh\s*dasa?\b|\bdasa\b"),
    ("Suman Sharma", r"suman"),
    ("Sheel Vardhan Singh", r"\bsheel|\bshil\s*vardhan"),
    ("Lt Gen Raj Shukla", r"shukla|sukhla"),
    ("BB Swain", r"swain"),
    ("Sujata Chaturvedi", r"suja(?:t|th)a|chaturvedi"),
    ("Anuradha Prasad", r"anuradha"),
    ("Preeti Sudan", r"preeti|sudan"),
    ("Ajay Kumar", r"aj[ae]y\s*kumar"),
]
BOARD_RES = [(name, re.compile(rx, re.I)) for name, rx in BOARDS]

QUESTION_LINE = re.compile(r"(?m)^\s*(?:[-*•]\s*)?(?:Q\.?\s*\d*|\d+)\s*[.):\-]")
REQUEST_POST = re.compile(r"you are requested to share|share (?:ur|your) interview", re.I)
FIELD = r"^\s*[*_]*\s*(?:\d+[.)]\s*)?{label}[*_]*\b[^\n:\-–~—]{{0,25}}[:\-–~—]+\s*(?P<v>[^\n]+)"
NAME_LINE = re.compile(FIELD.format(label="name"), re.I | re.M)
DATE_LINE = re.compile(FIELD.format(label=r"(?:interview\s*)?date(?:\s*of\s*interview)?"), re.I | re.M)
DAF_LINE = re.compile(FIELD.format(label=r"(?:key\s*)?(?:daf|key\s*words?|keywords|pointers)"), re.I | re.M)
OPTIONAL_LINE = re.compile(FIELD.format(label=r"opt(?:ional)?"), re.I | re.M)
OPTIONAL_INLINE = re.compile(r"([A-Za-z][A-Za-z &]{2,30}?)\s+optional\b", re.I)
PT_MARKS = re.compile(r"(?:PT|personality\s*test|interview)\s*(?:marks?|score)\s*[:\-–=]*\s*(\d{3})"
                      r"|scored\s*(\d{3})\s*(?:marks\s*)?in\s*(?:the\s*)?(?:PT|interview|personality)", re.I)
IFOS = re.compile(r"\bifos\b|\bifs\b|forest\s*service", re.I)
# Section headers inside a transcript: "Chairman", "M1", "Member 2 (lady)", "Chairperson -", ...
SECTION = re.compile(
    r"(?im)^\s*[-*•#>\[\] ]*(?:chair(?:man|person|woman)?|member\s*[-–]?\s*\d|m\s?[-–]?\s?\d|lady\s*member|"
    r"(?:1st|2nd|3rd|4th|first|second|third|fourth)\s*member)\b[^\n]{0,40}$")

MIN_CHARS = 600
MIN_QUESTION_SIGNALS = 5
CHUNK_CHARS = 1600


def question_signals(text: str) -> int:
    return text.count("?") + len(QUESTION_LINE.findall(text))


def board_of(text: str) -> str:
    head = text[:700]
    # Prefer a line that names the board explicitly; fall back to any chairperson name in the header.
    lines = [ln for ln in head.splitlines() if re.search(r"board|chair|panel", ln, re.I)] + [head]
    for chunk in lines:
        for name, rx in BOARD_RES:
            if rx.search(chunk):
                return name
    return "Unknown"


def classify(unit: dict) -> str | None:
    """None if this is a clearly marked transcript, else the reason it goes on hold."""
    text = unit["text"]
    head = text[:700]
    if REQUEST_POST.search(head):
        return "admin request"
    if len(text) < MIN_CHARS:
        return "too short"
    if question_signals(text) < MIN_QUESTION_SIGNALS and len(SECTION.findall(text)) < 2:
        return "no questions or member sections"
    titled = "transcript" in head[:80].lower() and _header_hits(text) >= 1
    if _header_hits(text) < 2 and not BOARD_NAME.search(head) and not titled:
        return "no transcript header"
    if len(NAME_LINE.findall(text)) >= 2 and len(re.findall(r"(?im)^\s*[*_]*board\b", text)) >= 2:
        return "may contain more than one transcript"
    return None


def cse_year(posted_at: str) -> int:
    """Personality tests for CSE year N run Dec(N) - Apr(N+1); transcripts get posted soon after."""
    d = date.fromisoformat(posted_at[:10])
    return d.year if d.month >= 11 else d.year - 1


def _field(rx: re.Pattern, text: str, limit: int = 160) -> str | None:
    m = rx.search(text[:900])
    if not m:
        return None
    v = m.group("v").strip(" *_-–:")
    return v[:limit] or None


def metadata(unit: dict) -> dict:
    text = unit["text"]
    optional = _field(OPTIONAL_LINE, text, 60)
    if not optional:
        m = OPTIONAL_INLINE.search(text[:900])
        optional = m.group(1).strip() if m else None
    marks = None
    for m in PT_MARKS.finditer(text):
        v = int(m.group(1) or m.group(2))
        if 50 <= v <= 275:
            marks = v
    return {
        "board": board_of(text),
        "alias": _field(NAME_LINE, text, 60),
        "interview_date": _field(DATE_LINE, text, 60),
        "daf": _field(DAF_LINE, text, 400),
        "optional_subject": optional,
        "pt_marks": marks,
        "exam": "IFoS" if IFOS.search(text[:600]) else "CSE",
        "cse_year": cse_year(unit["posted_at"]),
    }


def chunks(text: str) -> list[dict]:
    """Split at member sections (Chairman / M1 / ...), then cap each piece at ~CHUNK_CHARS on paragraph lines."""
    cuts = [m.start() for m in SECTION.finditer(text)]
    bounds = [0] + [c for c in cuts if c > 0] + [len(text)]
    sections = []
    for a, b in zip(bounds, bounds[1:]):
        piece = text[a:b].strip()
        if piece:
            first = piece.splitlines()[0].strip(" *_-#:>[]")[:40]
            label = "header" if a == 0 and cuts and cuts[0] > 0 else first if SECTION.match(piece) else "text"
            sections.append((label, piece))
    out = []
    for label, piece in sections:
        buf = ""
        for line in piece.splitlines(keepends=True):
            if len(buf) + len(line) > CHUNK_CHARS and buf.strip():
                out.append({"section": label, "text": buf.strip()})
                buf = ""
            buf += line
        if buf.strip():
            out.append({"section": label, "text": buf.strip()})
    return out
