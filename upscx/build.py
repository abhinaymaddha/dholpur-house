"""extracted/*.json + units.jsonl -> out/transcripts.jsonl, out/questions.jsonl, out/summary.txt."""
from __future__ import annotations

import json
from collections import Counter
from datetime import date

from .common import EXTRACTED, OUT, RAW, UNITS, read_jsonl, write_jsonl

CHANNEL = "https://t.me/csetranscripts"


def _cse_year(interview_date: str | None, posted_at: str) -> int:
    """Interviews for CSE year N run Dec(N) - Apr(N+1)."""
    try:
        d = date.fromisoformat(interview_date) if interview_date else None
    except ValueError:
        d = None
    d = d or date.fromisoformat(posted_at[:10])
    return d.year if d.month >= 10 else d.year - 1


def run() -> None:
    units = {u["unit_id"]: u for u in read_jsonl(UNITS)}
    transcripts, questions, skipped = [], [], Counter()
    for uid, unit in units.items():
        f = EXTRACTED / f"{uid}.json"
        if not f.exists():
            skipped["not extracted"] += 1
            continue
        x = json.loads(f.read_text(encoding="utf-8"))
        if not x["is_transcript"]:
            skipped[f"not a transcript: {x.get('non_transcript_kind') or 'other'}"] += 1
            continue
        qs = x.pop("questions")
        meta = x.pop("_meta")
        t = {
            "transcript_id": uid,
            "message_ids": unit["message_ids"],
            "telegram_url": f"{CHANNEL}/{unit['message_ids'][0]}",
            "posted_at": unit["posted_at"],
            "cse_year": _cse_year(x.get("interview_date"), unit["posted_at"]),
            "reactions": unit["reactions"],
            "duplicates": unit.get("duplicate_of_this", []),
            **{k: v for k, v in x.items() if k not in ("is_transcript", "non_transcript_kind")},
            "question_count": len(qs),
            "model": meta["model"],
        }
        transcripts.append(t)
        for q in qs:
            questions.append({
                "question_id": f"{uid}-q{q['seq']}",
                "transcript_id": uid,
                "board": t["board"], "cse_year": t["cse_year"], "exam": t["exam"],
                "optional_subject": t["optional_subject"], "home_state": t["home_state"],
                **q,
            })

    write_jsonl(OUT / "transcripts.jsonl", transcripts)
    write_jsonl(OUT / "questions.jsonl", questions)

    # Coverage: every raw message is either in a kept unit, a dropped duplicate, or noise.
    raw_ids = {m["id"] for m in read_jsonl(RAW)}
    in_units = {i for u in units.values() for i in u["message_ids"]}
    lines = [
        f"raw messages: {len(raw_ids)} | in units: {len(in_units)} | not in a unit (noise/duplicate): {len(raw_ids - in_units)}",
        f"units: {len(units)} | transcripts: {len(transcripts)} | questions: {len(questions)}",
        "skipped: " + ", ".join(f"{k}={v}" for k, v in skipped.most_common()),
        "", "by exam/year: " + ", ".join(f"{k}={v}" for k, v in Counter(
            f"{t['exam']} {t['cse_year']}" for t in transcripts).most_common()),
        "", "boards: " + ", ".join(f"{k}={v}" for k, v in Counter(t["board"] for t in transcripts).most_common()),
        "", "topics: " + ", ".join(f"{k}={v}" for k, v in Counter(q["topic"] for q in questions).most_common()),
        "", f"daf-linked questions: {sum(q['daf_linked'] for q in questions)} / {len(questions)}",
        f"with PT marks: {sum(t['pt_marks'] is not None for t in transcripts)} | with AIR: {sum(t['air'] is not None for t in transcripts)}",
        "confidence: " + ", ".join(f"{k}={v}" for k, v in Counter(t["extraction_confidence"] for t in transcripts).most_common()),
        f"low-confidence ids: {[t['transcript_id'] for t in transcripts if t['extraction_confidence'] == 'low']}",
        f"zero-question transcripts: {[t['transcript_id'] for t in transcripts if not t['question_count']]}",
        f"board Other/Unknown: {[(t['transcript_id'], t['board_raw']) for t in transcripts if t['board'] in ('Other', 'Unknown')]}",
    ]
    (OUT / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
