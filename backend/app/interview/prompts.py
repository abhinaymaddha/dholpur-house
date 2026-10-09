"""Prompt templates and per-topic guidance, read from disk on every call so they can be tuned live.

Templates are markdown with {{placeholders}}. Topic files (prompts/topics/*.md) start with a small
header block:

    ---
    topic: International Relations
    source: mixed          # past | current | mixed | daf
    current_share: 0.7     # for mixed: share of main questions drawn from current affairs
    ---
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


@dataclass(frozen=True)
class Topic:
    name: str
    slug: str
    source: str
    current_share: float
    guidance: str


def render(template: str, **values: str) -> str:
    text = (PROMPTS_DIR / f"{template}.md").read_text(encoding="utf-8")
    missing = set(_PLACEHOLDER.findall(text)) - values.keys()
    if missing:
        raise KeyError(f"{template}.md needs {sorted(missing)}")
    return _PLACEHOLDER.sub(lambda m: values[m.group(1)], text)


def _parse(path: Path) -> Topic:
    raw = path.read_text(encoding="utf-8")
    meta, body = {}, raw
    if raw.startswith("---"):
        head, _, body = raw[3:].partition("\n---")
        for line in head.strip().splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.split("#")[0].strip()
    return Topic(name=meta.get("topic", path.stem), slug=path.stem, source=meta.get("source", "past"),
                 current_share=float(meta.get("current_share", 0) or 0), guidance=body.strip())


def topics() -> dict[str, Topic]:
    return {t.name: t for t in map(_parse, sorted((PROMPTS_DIR / "topics").glob("*.md")))}


def topic(name: str) -> Topic:
    all_topics = topics()
    if name not in all_topics:
        raise KeyError(f"Unknown topic {name!r}")
    return all_topics[name]
