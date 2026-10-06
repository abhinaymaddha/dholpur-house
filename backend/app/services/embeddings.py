"""Local text embeddings via fastembed (ONNX, CPU). The model downloads once on first use."""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from app.config import settings


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding   # imported lazily: loading the model takes a few seconds
    return TextEmbedding(settings.embed_model, cache_dir=settings.embed_cache_dir)


def embed(texts: list[str], batch_size: int = 64) -> list[np.ndarray]:
    return list(_model().embed(texts, batch_size=batch_size))


def embed_one(text: str) -> np.ndarray:
    return embed([text])[0]
