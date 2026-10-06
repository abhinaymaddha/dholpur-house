"""Load a Telegram Desktop export into Postgres.

    python -m app.ingest "<path to ChatExport folder>"

Re-running replaces everything: the export is the source of truth.
"""
from __future__ import annotations

import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from psycopg import connect

from app.config import settings
from app.database import init_schema
from app.services.embeddings import embed
from .parse import parse_export
from .segment import build_units, dedupe
from .transcripts import chunks, classify, metadata


def main(export_dir: str) -> None:
    t0 = time.time()
    msgs = parse_export(Path(export_dir).expanduser())
    units, noise = build_units(msgs)
    n_units = len(units)
    units = dedupe(units)
    accepted, held = [], []
    for u in units:
        reason = classify(u)
        (held.append((u, reason)) if reason else accepted.append(u))
    print(f"{len(msgs)} messages | {len(noise)} noise | {n_units} units | {len(units)} after dedupe")
    print(f"accepted {len(accepted)} | held {len(held)}: {dict(Counter(r for _, r in held))}")

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
    print(f"{len(chunk_rows)} chunks; embedding...")
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
    boards = Counter(r["board"] for r in rows)
    print(f"boards: {dict(boards.most_common())}")
    print(f"loaded in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
