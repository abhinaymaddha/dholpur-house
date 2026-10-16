"""The one entry point every LLM flow uses. Callers pick a model slot (model_1, model_2, ...); the slot's
provider in models.toml decides which adapter runs: Anthropic's SDK, or an OpenAI-compatible API."""

from __future__ import annotations

from collections.abc import Iterator

from app.models_config import ConfigError, get_model
from app.services.llm_errors import AdapterError


class LLMError(RuntimeError):
    pass


def _adapter(kind: str):
    if kind == "anthropic":
        from app.services import llm_anthropic as adapter   # imported lazily: only needed when configured
    else:
        from app.services import llm_openai as adapter
    return adapter


def complete_json(model_key: str, messages: list[dict], schema: dict, name: str) -> dict:
    """One non-streamed call that returns JSON matching `schema`."""
    try:
        m = get_model(model_key)
        adapter = _adapter(m.provider.kind)
        return adapter.complete_json(m, messages, schema, name)
    except (ConfigError, AdapterError) as e:
        raise LLMError(str(e)) from e


def stream_text(model_key: str, messages: list[dict]) -> Iterator[str]:
    """Stream plain-text deltas."""
    try:
        m = get_model(model_key)
        adapter = _adapter(m.provider.kind)
        yield from adapter.stream_text(m, messages)
    except (ConfigError, AdapterError) as e:
        raise LLMError(str(e)) from e
