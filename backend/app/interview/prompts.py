"""Prompt templates and per-topic guidance, read from disk on every call so they can be tuned live.

Templates are markdown with {{placeholders}}. Topic files (prompts/topics/*.md) start with a small
header block:

    ---
    topic: International Relations
    news: yes          # include recent current-affairs articles when writing questions
    daf: required      # optional: the topic can't be asked without the candidate's DAF
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
    news: bool
    needs_daf: bool
    guidance: str

    @property
    def testing(self) -> str:
        """The 'What the board is testing' paragraph, used as a search query for similar past questions."""
        part = self.guidance.split("## What the board is testing", 1)[-1]
        return part.split("##", 1)[0].strip()


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
    return Topic(name=meta.get("topic", path.stem), slug=path.stem, news=meta.get("news", "no") == "yes",
                 needs_daf=meta.get("daf") == "required", guidance=body.strip())


def topics() -> dict[str, Topic]:
    return {t.name: t for t in map(_parse, sorted((PROMPTS_DIR / "topics").glob("*.md")))}


def topic(name: str) -> Topic:
    all_topics = topics()
    if name not in all_topics:
        raise KeyError(f"Unknown topic {name!r}")
    return all_topics[name]
