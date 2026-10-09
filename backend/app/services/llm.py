"""OpenRouter client used by every LLM flow. Callers pick a model slot from models.toml (model_1, model_2, ...)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import requests

from app.config import settings
from app.models_config import get_model

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMError(RuntimeError):
    pass


def _body(model_key: str, messages: list[dict], **extra) -> dict:
    m = get_model(model_key)
    body = {"model": m.id, "max_tokens": m.max_tokens, "messages": messages, **extra}
    if m.reasoning_effort:
        body["reasoning"] = {"effort": m.reasoning_effort, "exclude": True}
    if m.temperature is not None:
        body["temperature"] = m.temperature
    return body


def _headers() -> dict:
    if not settings.openrouter_api_key:
        raise LLMError("OPENROUTER_API_KEY is not configured on the server")
    return {"Authorization": f"Bearer {settings.openrouter_api_key}", "X-Title": settings.app_name}


def complete_json(model_key: str, messages: list[dict], schema: dict, name: str) -> dict:
    """One non-streamed call that must return JSON matching `schema` (OpenRouter structured outputs)."""
    body = _body(model_key, messages, response_format={
        "type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}})
    body["provider"] = {"require_parameters": True}   # only providers that honour response_format
    try:
        r = requests.post(OPENROUTER_URL, json=body, headers=_headers(), timeout=(10, 300))
    except requests.RequestException as e:
        raise LLMError(f"Could not reach OpenRouter: {e}") from e
    if r.status_code != 200:
        raise LLMError(f"OpenRouter returned {r.status_code}: {r.text[:300]}")
    data = r.json()
    if "error" in data:
        raise LLMError(str(data["error"].get("message", data["error"])))
    choice = data["choices"][0]
    if choice.get("finish_reason") not in ("stop", "end_turn"):
        raise LLMError(f"The model stopped early ({choice.get('finish_reason')}); try again")
    try:
        return json.loads(choice["message"]["content"])
    except (TypeError, json.JSONDecodeError) as e:
        raise LLMError("The model returned malformed JSON; try again") from e


def stream_text(model_key: str, messages: list[dict]) -> Iterator[str]:
    """Stream plain-text deltas."""
    body = _body(model_key, messages, stream=True)
    with requests.post(OPENROUTER_URL, json=body, headers=_headers(), stream=True, timeout=(10, 300)) as r:
        if r.status_code != 200:
            raise LLMError(f"OpenRouter returned {r.status_code}: {r.text[:300]}")
        r.encoding = "utf-8"   # text/event-stream has no charset, and requests would assume Latin-1
        for raw in r.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data: "):
                continue   # blank keep-alives and ": OPENROUTER PROCESSING" comments
            data = raw[len("data: "):]
            if data == "[DONE]":
                break
            event = json.loads(data)
            if "error" in event:
                raise LLMError(str(event["error"].get("message", event["error"])))
            delta = (event.get("choices") or [{}])[0].get("delta", {}).get("content")
            if delta:
                yield delta
