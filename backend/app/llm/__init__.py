"""LLM access for the rest of the app. Flows name a model slot (model_1, model_2, ...) from models.toml;
the slot's provider decides which LLMProvider subclass does the work.

    from app import llm
    data = llm.complete_json("model_3", messages, schema, "evaluation")
    for delta in llm.stream_text("model_1", messages): ...
"""

from __future__ import annotations

from collections.abc import Iterator

from app.llm.registry import provider_for
from app.models_config import get_model


def complete_json(model_key: str, messages: list[dict], schema: dict, name: str) -> dict:
    model = get_model(model_key)
    return provider_for(model.provider).complete_json(model, messages, schema, name)


def stream_text(model_key: str, messages: list[dict]) -> Iterator[str]:
    model = get_model(model_key)
    yield from provider_for(model.provider).stream_text(model, messages)
