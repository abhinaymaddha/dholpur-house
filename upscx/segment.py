"""raw_messages.jsonl -> units.jsonl.

A "unit" is one candidate transcript (or one piece of noise). Telegram caps a message at
4096 chars, so long transcripts arrive as 2-4 consecutive messages posted seconds apart,
and marks/acknowledgement footers often follow as a separate message. We stitch those,
drop obvious channel noise, and collapse transcripts the admins reposted.
"""
from __future__ import annotations

import re
from datetime import datetime

from .common import RAW, UNITS, read_jsonl, write_jsonl

# Header lines a transcript opens with ("Name:", "Board -", "DAF keywords", ...).
HEADER = re.compile(
    r"^\s*(?:\d+[.)]\s*)?(?:name|board|chair(?:man|person)?|daf|key\s*words?|keywords|optional|opt|"
    r"interview\s*date|date|duration|session)\b[^\n]{0,40}[:\-–]",
    re.I | re.M,
)
CONTINUATION_GAP_S = 120     # parts of one transcript are posted within seconds of each other
MIN_UNIT_CHARS = 300         # below this, a headerless unit is announcement chatter, not a transcript
NOISE_SOURCES = {"CSE Updates", "Prince Sonu Mayank, IPS"}   # forwarded official-notice channels
DUP_JACCARD = 0.6


# Header fields that never appear mid-transcript ("Chairman:" does, when the chair resumes questioning).
OPENING_HEADER = re.compile(
    r"^\s*(?:\d+[.)]\s*)?(?:name|board|daf|key\s*words?|keywords|optional|interview\s*date|date|duration)\b"
    r"[^\n]{0,40}[:\-–]",
    re.I | re.M,
)
# Chairperson surnames, for headers written without a "Board:" label ("BB Swain sir\nOptional History").
BOARD_NAME = re.compile(
    r"\b(verma|varma|dasa|suman|sheel\s*[vw]ardhan|shukla|swain|sujat?ha|chaturvedi|anuradha|preeti|sudan)\b", re.I)
DATE_LEAD = re.compile(
    r"^\W*(?:\d{1,2}(?:st|nd|rd|th)?\s*(?:jan|feb|mar|apr|dec)|\d{1,2}[./-]\d{1,2}[./-]\d{2,4})", re.I)
SESSION_WORDS = re.compile(r"board|session|forenoon|afternoon|to go|\b(?:FN|AN)\b", re.I)
SPLIT_LIMIT = 3300   # a message this long was likely cut by Telegram's 4096-char cap


def _header_hits(text: str) -> int:
    return len(HEADER.findall(text[:600]))


def _strong_start(text: str) -> bool:
    """Evidence of a new transcript strong enough to override 'previous message was cut off'."""
    head = text[:150]
    return (_header_hits(text) >= 2
            or "transcript" in head[:80].lower()
            or bool(BOARD_NAME.search(head) and (SESSION_WORDS.search(head) or DATE_LEAD.match(head))))


def _starts_transcript(text: str) -> bool:
    head = text[:250]
    return (_strong_start(text)
            or bool(OPENING_HEADER.search(head))
            or bool(BOARD_NAME.search(head))
            or bool(DATE_LEAD.match(head))
            or "transcript" in head[:80].lower())


def _shingles(text: str, k: int = 5) -> set[int]:
    words = re.findall(r"\w+", text.lower())
    return {hash(" ".join(words[i:i + k])) for i in range(max(1, len(words) - k + 1))}


def build_units(msgs: list[dict]) -> tuple[list[dict], list[dict]]:
    units: list[dict] = []
    noise: list[dict] = []
    cur = None
    prev_t = None
    for m in msgs:
        t = datetime.fromisoformat(m["posted_at"])
        text = m["text"]
        if not text or m["forwarded_from"] in NOISE_SOURCES:
            noise.append({"id": m["id"], "reason": "empty" if not text else "official-forward"})
            prev_t = t
            continue
        gap = (t - prev_t).total_seconds() if prev_t else None
        prev_cut = bool(cur) and len(cur["parts"][-1]) >= SPLIT_LIMIT
        new_start = _strong_start(text) if prev_cut else _starts_transcript(text)
        if cur and gap is not None and gap <= CONTINUATION_GAP_S and not new_start:
            cur["message_ids"].append(m["id"])
            cur["parts"].append(text)
        else:
            cur = {"message_ids": [m["id"]], "parts": [text], "posted_at": m["posted_at"],
                   "forwarded_from": m["forwarded_from"], "reactions": m["reactions"]}
            units.append(cur)
        prev_t = t

    kept = []
    for u in units:
        u["text"] = "\n\n".join(u.pop("parts"))
        u["unit_id"] = f"u{u['message_ids'][0]}"
        if len(u["text"]) < MIN_UNIT_CHARS and not _starts_transcript(u["text"]):
            noise.extend({"id": i, "reason": "short"} for i in u["message_ids"])
        else:
            kept.append(u)
    return kept, noise


def dedupe(units: list[dict]) -> list[dict]:
    """Admins sometimes repost a transcript (e.g. after adding PT marks). Keep the longest copy."""
    sh = [_shingles(u["text"]) for u in units]
    order = sorted(range(len(units)), key=lambda i: -len(units[i]["text"]))
    dropped = set()
    for a_pos, a in enumerate(order):
        if a in dropped:
            continue
        for b in order[a_pos + 1:]:
            if b in dropped:
                continue
            if len(sh[b]) < 0.4 * len(sh[a]):
                # b is much shorter; it can still be a partial repost if most of it is inside a
                containment = len(sh[a] & sh[b]) / max(1, len(sh[b]))
                if containment < 0.9:
                    continue
            else:
                inter = len(sh[a] & sh[b])
                if inter / max(1, len(sh[a] | sh[b])) < DUP_JACCARD:
                    continue
            dropped.add(b)
            units[a].setdefault("duplicate_of_this", []).append(units[b]["unit_id"])
    return [u for i, u in enumerate(units) if i not in dropped]


def run() -> None:
    msgs = read_jsonl(RAW)
    units, noise = build_units(msgs)
    before = len(units)
    units = dedupe(units)
    n = write_jsonl(UNITS, units)
    covered = {i for u in units for i in u["message_ids"]}
    dup_ids = sum(len(u.get("duplicate_of_this", [])) for u in units)
    print(f"{len(msgs)} messages -> {before} units -> {n} after dedupe ({dup_ids} duplicate units dropped)")
    print(f"noise messages: {len(noise)}; multi-message units: {sum(len(u['message_ids']) > 1 for u in units)}")
    print(f"messages in kept units: {len(covered)}; total chars: {sum(len(u['text']) for u in units):,}")
