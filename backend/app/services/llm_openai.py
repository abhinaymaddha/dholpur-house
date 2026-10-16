"""Adapter for OpenAI-style chat-completions APIs: OpenRouter, OpenAI, and any compatible server."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator

import requests

from app.models_config import ModelConfig
from app.services.llm_errors import AdapterError



def _schema_hint(schema: dict) -> str:
    return ("\n\nRespond with a single JSON object only (no prose, no code fences) matching this JSON schema:\n"
            + json.dumps(schema))


def build_body(m: ModelConfig, messages: list[dict], schema: dict | None = None, name: str = "result",
               stream: bool = False) -> dict:
    kind = m.provider.kind
    body: dict = {"model": m.id, "messages": [dict(x) for x in messages]}
    body["max_completion_tokens" if kind == "openai" else "max_tokens"] = m.max_tokens
    if m.reasoning_effort:
        if kind == "openrouter":
            body["reasoning"] = {"effort": m.reasoning_effort, "exclude": True}
        else:
            body["reasoning_effort"] = m.reasoning_effort
    if m.temperature is not None:
        body["temperature"] = m.temperature
    if stream:
        body["stream"] = True
    if schema is not None:
        if m.json_mode == "schema":
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}
            if kind == "openrouter":
                body["provider"] = {"require_parameters": True}   # only providers that honour response_format
        else:
            body["messages"][-1]["content"] += _schema_hint(schema)
            if m.json_mode == "object":
                body["response_format"] = {"type": "json_object"}
    return body


def _post(m: ModelConfig, body: dict, stream: bool = False) -> requests.Response:
    headers = {"Authorization": f"Bearer {m.provider.key()}"}
    if m.provider.kind == "openrouter":
        headers["X-Title"] = "Dholpur House"
    url = m.provider.base_url.rstrip("/") + "/chat/completions"
    try:
        r = requests.post(url, json=body, headers=headers, stream=stream, timeout=(10, 300))
    except requests.RequestException as e:
        raise AdapterError(f"Could not reach {m.provider.name}: {e}") from e
    if r.status_code != 200:
        raise AdapterError(f"{m.provider.name} returned {r.status_code}: {r.text[:300]}")
    return r


def _parse_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text or "", re.S)   # tolerate code fences or stray prose (prompt mode)
        if match:
            return json.loads(match.group(0))
        raise


def complete_json(m: ModelConfig, messages: list[dict], schema: dict, name: str) -> dict:
    data = _post(m, build_body(m, messages, schema, name)).json()
    if "error" in data:
        raise AdapterError(str(data["error"].get("message", data["error"])))
    choice = data["choices"][0]
    if choice.get("finish_reason") not in ("stop", "end_turn"):
        raise AdapterError(f"The model stopped early ({choice.get('finish_reason')}); try again")
    try:
        return _parse_json(choice["message"]["content"])
    except (TypeError, json.JSONDecodeError) as e:
        raise AdapterError("The model returned malformed JSON; try again") from e


def stream_text(m: ModelConfig, messages: list[dict]) -> Iterator[str]:
    with _post(m, build_body(m, messages, stream=True), stream=True) as r:
        r.encoding = "utf-8"   # text/event-stream has no charset, and requests would assume Latin-1
        for raw in r.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data: "):
                continue   # blank keep-alives and ": PROCESSING" comments
            data = raw[len("data: "):]
            if data == "[DONE]":
                break
            event = json.loads(data)
            if "error" in event:
                raise AdapterError(str(event["error"].get("message", event["error"])))
            delta = (event.get("choices") or [{}])[0].get("delta", {}).get("content")
            if delta:
                yield delta
