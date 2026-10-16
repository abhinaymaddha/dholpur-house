"""Test doubles: a deterministic embedder and a scripted LLM provider."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterator

import numpy as np

from app.llm.base import LLMProvider
from app.llm.registry import register

DIM = 384


class FakeEmbedder:
    """Bag-of-words hashed into 384 dims and normalised: texts sharing words are close, as with a real model."""

    def embed(self, texts, batch_size: int = 64) -> Iterator[np.ndarray]:
        for text in texts:
            v = np.zeros(DIM, dtype=np.float32)
            for word in re.findall(r"\w+", text.lower()):
                v[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1
            v[0] += 0.01   # never a zero vector (cosine distance needs a length)
            yield v / np.linalg.norm(v)


@register
class FakeProvider(LLMProvider):
    """kind = "fake". Tests set `json[name]` (schema name -> callable(messages) -> dict) and `text`."""

    kind = "fake"
    requires_base_url = False

    json: dict[str, Callable[[list[dict]], dict]] = {}
    text: list[str] = ["An answer ", "citing [S1]."]
    calls: list[dict] = []
    error: Exception | None = None

    @classmethod
    def reset(cls) -> None:
        cls.json, cls.text, cls.calls, cls.error = {}, ["An answer ", "citing [S1]."], [], None

    def complete_json(self, model, messages, schema, name):
        type(self).calls.append({"model": model.key, "name": name, "messages": messages})
        if type(self).error:
            raise type(self).error
        return type(self).json[name](messages)

    def stream_text(self, model, messages):
        type(self).calls.append({"model": model.key, "name": "stream", "messages": messages})
        if type(self).error:
            raise type(self).error
        yield from type(self).text
