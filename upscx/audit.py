"""Side-by-side HTML for spot-checking extraction: original text vs extracted fields and questions."""
from __future__ import annotations

import html
import json
import random

from .common import EXTRACTED, OUT, UNITS, read_jsonl

CSS = """
body{font:14px/1.5 -apple-system,system-ui,sans-serif;margin:0;background:#f6f6f4;color:#1d1d1b}
header{padding:16px 24px;background:#fff;border-bottom:1px solid #ddd;position:sticky;top:0}
section{display:grid;grid-template-columns:1fr 1.3fr;gap:16px;padding:16px 24px;border-bottom:1px solid #ddd}
pre{white-space:pre-wrap;background:#fff;border:1px solid #e3e3e0;padding:12px;margin:0;max-height:80vh;overflow:auto}
.card{background:#fff;border:1px solid #e3e3e0;padding:12px;max-height:80vh;overflow:auto}
table{border-collapse:collapse;width:100%}td,th{border-top:1px solid #eee;padding:4px 6px;text-align:left;vertical-align:top}
th{font-weight:600;color:#666;font-size:12px}.k{color:#666;width:150px}.low{background:#fde8e8}.tag{color:#666;font-size:12px}
h2{font-size:15px;margin:0 0 8px}label{font-size:13px;margin-left:12px}
"""

HEADER_FIELDS = ["exam", "alias", "interview_date", "session", "order_in_session", "board", "board_raw",
                 "duration_minutes", "optional_subject", "home_state", "hometown", "education", "work_experience",
                 "current_service", "hobbies", "daf_keywords", "daf_items_not_asked", "pt_marks", "air", "mocks",
                 "board_behaviour", "candidate_takeaways", "extraction_confidence", "extraction_notes"]


def _v(v) -> str:
    if v is None or v == []:
        return "<span class=tag>—</span>"
    return html.escape(", ".join(map(str, v)) if isinstance(v, list) else str(v))


def _section(unit: dict, x: dict) -> str:
    rows = "".join(f"<tr><td class=k>{k}</td><td>{_v(x.get(k))}</td></tr>" for k in HEADER_FIELDS)
    qrows = "".join(
        f"<tr><td>{q['seq']}</td><td>{q['member']}{' ♀' if q['member_gender'] == 'female' else ''}</td>"
        f"<td>{'↳ ' if q['is_followup'] else ''}{html.escape(q['question'])}"
        f"{'<br><span class=tag>' + html.escape(q['question_en']) + '</span>' if q['question_en'] else ''}"
        f"{'<br><i class=tag>A: ' + html.escape(q['answer_notes']) + '</i>' if q['answer_notes'] else ''}</td>"
        f"<td>{html.escape(q['topic'])}<br><span class=tag>{_v(q['tags'])}</span></td>"
        f"<td>{'DAF: ' + html.escape(q['daf_hook'] or 'yes') if q['daf_linked'] else ''}</td></tr>"
        for q in x.get("questions", [])
    )
    low = " low" if x.get("extraction_confidence") == "low" or not x.get("is_transcript") else ""
    title = (f"{unit['unit_id']} · msgs {unit['message_ids']} · posted {unit['posted_at'][:10]} · "
             f"{'TRANSCRIPT' if x['is_transcript'] else 'NOT TRANSCRIPT: ' + str(x.get('non_transcript_kind'))} · "
             f"{len(x.get('questions', []))} questions")
    return (f"<section class='{low}'><div><h2>{html.escape(title)}</h2><pre>{html.escape(unit['text'])}</pre></div>"
            f"<div class=card><table>{rows}</table><br><table><tr><th>#</th><th>member</th><th>question</th>"
            f"<th>topic / tags</th><th>DAF</th></tr>{qrows}</table></div></section>")


def run(n: int, seed: int = 1) -> None:
    units = {u["unit_id"]: u for u in read_jsonl(UNITS)}
    done = [f.stem for f in EXTRACTED.glob("*.json")]
    pick = random.Random(seed).sample(done, min(n, len(done)))
    pick.sort(key=lambda i: int(i[1:]))
    body = "".join(_section(units[i], json.loads((EXTRACTED / f"{i}.json").read_text(encoding="utf-8"))) for i in pick)
    page = (f"<!doctype html><meta charset=utf-8><title>Extraction audit</title><style>{CSS}</style>"
            f"<header><b>Extraction audit</b> — {len(pick)} of {len(done)} extracted units. "
            f"Check: every question captured, member mapping, board, DAF fields, no invented content.</header>{body}")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "audit.html"
    path.write_text(page, encoding="utf-8")
    print(f"wrote {path}")
