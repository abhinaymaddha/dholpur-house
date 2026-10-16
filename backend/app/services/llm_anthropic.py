"""Adapter for Anthropic's Claude API, using the official `anthropic` SDK."""

from __future__ import annotations

import json
from collections.abc import Iterator
from functools import lru_cache

import anthropic

from app.models_config import ModelConfig
from app.services.llm_errors import AdapterError

FALLBACK_BETA = "server-side-fallback-2026-07-01"



@lru_cache(maxsize=8)
def _client(api_key: str, base_url: str | None) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key, base_url=base_url) if base_url else anthropic.Anthropic(api_key=api_key)


def build_params(m: ModelConfig, messages: list[dict], schema: dict | None = None) -> dict:
    """Messages API parameters. System messages move to `system`; the schema goes in output_config.format."""
    system = "\n\n".join(x["content"] for x in messages if x["role"] == "system")
    params: dict = {"model": m.id, "max_tokens": m.max_tokens,
                    "messages": [x for x in messages if x["role"] != "system"]}
    if system:
        params["system"] = system
    output_config: dict = {}
    if m.reasoning_effort:
        output_config["effort"] = m.reasoning_effort
    if schema is not None:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    if output_config:
        params["output_config"] = output_config
    if m.temperature is not None:
        params["temperature"] = m.temperature
    if m.fallbacks:
        params |= {"betas": [FALLBACK_BETA], "fallbacks": m.fallbacks}
    return params


def _messages_api(m: ModelConfig, params: dict):
    client = _client(m.provider.key(), m.provider.base_url)
    return client.beta.messages if "betas" in params else client.messages


def _check(message) -> None:
    if message.stop_reason == "refusal":
        category = getattr(message.stop_details, "category", None) if message.stop_details else None
        raise AdapterError(f"Claude declined this request{f' ({category})' if category else ''}")
    if message.stop_reason == "max_tokens":
        raise AdapterError("The model stopped early (max_tokens); try again or raise max_tokens")


def complete_json(m: ModelConfig, messages: list[dict], schema: dict, name: str) -> dict:
    params = build_params(m, messages, schema)
    try:
        message = _messages_api(m, params).create(**params)
    except anthropic.RateLimitError as e:
        raise AdapterError("Claude API rate limit reached; try again shortly") from e
    except anthropic.APIStatusError as e:
        raise AdapterError(f"Claude API returned {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise AdapterError(f"Could not reach the Claude API: {e}") from e
    _check(message)
    text = next((b.text for b in message.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AdapterError("The model returned malformed JSON; try again") from e


def stream_text(m: ModelConfig, messages: list[dict]) -> Iterator[str]:
    params = build_params(m, messages)
    try:
        with _messages_api(m, params).stream(**params) as stream:
            yield from stream.text_stream
            _check(stream.get_final_message())
    except anthropic.RateLimitError as e:
        raise AdapterError("Claude API rate limit reached; try again shortly") from e
    except anthropic.APIStatusError as e:
        raise AdapterError(f"Claude API returned {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise AdapterError(f"Could not reach the Claude API: {e}") from e
