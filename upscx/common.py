from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
RAW = DATA / "raw_messages.jsonl"
UNITS = DATA / "units.jsonl"
EXTRACTED = DATA / "extracted"          # one JSON file per unit, written by pilot/collect
OUT = DATA / "out"                      # transcripts.jsonl, questions.jsonl, reports


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n
