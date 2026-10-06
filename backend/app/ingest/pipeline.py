"""Telegram messages -> Postgres. Used by the CLI, the admin upload endpoint and first-start seeding.

Messages come from a Telegram Desktop HTML export or from the committed seed (JSONL of parsed
messages). Re-running replaces everything: the messages are the source of truth.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from psycopg import connect

from app.config import settings
from app.database import init_schema
from app.services.embeddings import embed

from .parse import parse_export
from .segment import build_units, dedupe
from .transcripts import chunks, classify, metadata


SEED_FILE = Path(__file__).resolve().parents[2] / "seed" / "csetranscripts_messages.jsonl"


def load_messages(source: Path) -> list[dict]:
    """A Telegram export folder (messages*.html) or a .jsonl file of parsed messages."""
    if source.is_file() and source.suffix == ".jsonl":
        with open(source, encoding="utf-8") as f:
            msgs = [json.loads(line) for line in f if line.strip()]
    else:
        msgs = parse_export(source)
    if not msgs:
        raise ValueError(f"no messages found in {source} (expected a Telegram export folder or a .jsonl file)")
    return msgs


def write_messages(msgs: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for m in msgs:
            f.write(json.dumps(m, ensure_ascii=False, sort_keys=True) + "\n")


def run_ingest(source: Path, log: Callable[[str], None] = print) -> dict:
    t0 = time.time()
    msgs = load_messages(source)
    units, noise = build_units(msgs)
    n_units = len(units)
    units = dedupe(units)
    accepted, held = [], []
    for u in units:
        reason = classify(u)
        (held.append((u, reason)) if reason else accepted.append(u))
    held_reasons = dict(Counter(r for _, r in held))
    log(f"{len(msgs)} messages | {len(noise)} noise | {n_units} units | {len(units)} after dedupe")
    log(f"accepted {len(accepted)} | held {len(held)}: {held_reasons}")

    rows, chunk_rows = [], []
    for u in accepted:
        meta = metadata(u)
        rows.append({
            "id": u["unit_id"], "message_ids": u["message_ids"],
            "posted_at": datetime.fromisoformat(u["posted_at"]),
            "telegram_url": f"{settings.telegram_channel}/{u['message_ids'][0]}",
            "reactions": u["reactions"], "duplicates": u.get("duplicates", []), "text": u["text"], **meta,
        })
        for seq, c in enumerate(chunks(u["text"])):
            chunk_rows.append({"transcript_id": u["unit_id"], "seq": seq, **c})
    log(f"{len(chunk_rows)} chunks; embedding...")
    vectors = embed([c["text"] for c in chunk_rows])

    with connect(settings.database_url, autocommit=False) as conn:
        init_schema(conn)
        conn.execute("TRUNCATE chunks, transcripts, held")
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO transcripts (id, message_ids, posted_at, telegram_url, board, alias, interview_date, daf,"
                " optional_subject, pt_marks, exam, cse_year, reactions, duplicates, text) VALUES"
                " (%(id)s, %(message_ids)s, %(posted_at)s, %(telegram_url)s, %(board)s, %(alias)s, %(interview_date)s,"
                " %(daf)s, %(optional_subject)s, %(pt_marks)s, %(exam)s, %(cse_year)s, %(reactions)s, %(duplicates)s,"
                " %(text)s)", rows)
            cur.executemany(
                "INSERT INTO held (id, reason, message_ids, posted_at, text) VALUES (%s, %s, %s, %s, %s)",
                [(u["unit_id"], r, u["message_ids"], datetime.fromisoformat(u["posted_at"]), u["text"])
                 for u, r in held])
            cur.executemany(
                "INSERT INTO chunks (transcript_id, seq, section, text, embedding) VALUES (%s, %s, %s, %s, %s)",
                [(c["transcript_id"], c["seq"], c["section"], c["text"], v) for c, v in zip(chunk_rows, vectors)])
        conn.commit()

    summary = {
        "messages": len(msgs), "units": len(units), "transcripts": len(rows), "held": len(held),
        "held_reasons": held_reasons, "chunks": len(chunk_rows),
        "boards": dict(Counter(r["board"] for r in rows).most_common()),
        "seconds": round(time.time() - t0),
    }
    log(f"loaded {summary['transcripts']} transcripts in {summary['seconds']}s")
    return summary
