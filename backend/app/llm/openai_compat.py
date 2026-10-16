"""Providers speaking the OpenAI chat-completions API: any compatible server, OpenAI, and OpenRouter.

The base class implements the protocol; subclasses override only the small hooks where a provider
differs (parameter names, extra request fields, headers).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator

import requests

from app.errors import ProviderError
from app.llm.base import LLMProvider
from app.models_config import ModelConfig


class OpenAICompatibleProvider(LLMProvider):
    """Groq, Together, DeepSeek, Mistral, Gemini's OpenAI endpoint, Ollama, vLLM, LM Studio, ..."""

    kind = "openai_compatible"
    max_tokens_field = "max_tokens"
    timeout = (10, 300)

    # ----- hooks for subclasses -----

    def reasoning_fields(self, effort: str) -> dict:
        return {"reasoning_effort": effort}

    def json_schema_fields(self) -> dict:
        """Extra request fields when a JSON schema is enforced."""
        return {}

    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.config.key()}"}

    # ----- protocol -----

    @staticmethod
    def schema_hint(schema: dict) -> str:
        return ("\n\nRespond with a single JSON object only (no prose, no code fences) matching this JSON schema:\n"
                + json.dumps(schema))

    def build_body(self, model: ModelConfig, messages: list[dict], schema: dict | None = None,
                   name: str = "result", stream: bool = False) -> dict:
        body: dict = {"model": model.id, "messages": [dict(m) for m in messages], self.max_tokens_field: model.max_tokens}
        if model.reasoning_effort:
            body |= self.reasoning_fields(model.reasoning_effort)
        if model.temperature is not None:
            body["temperature"] = model.temperature
        if stream:
            body["stream"] = True
        if schema is not None:
            if model.json_mode == "schema":
                body["response_format"] = {"type": "json_schema",
                                           "json_schema": {"name": name, "strict": True, "schema": schema}}
                body |= self.json_schema_fields()
            else:
                body["messages"][-1]["content"] += self.schema_hint(schema)
                if model.json_mode == "object":
                    body["response_format"] = {"type": "json_object"}
        return body

    def _post(self, body: dict, stream: bool = False) -> requests.Response:
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        try:
            r = requests.post(url, json=body, headers=self.headers(), stream=stream, timeout=self.timeout)
        except requests.RequestException as e:
            raise ProviderError(f"Could not reach {self.name}: {e}") from e
        if r.status_code != 200:
            raise ProviderError(f"{self.name} returned {r.status_code}: {r.text[:300]}")
        return r

    @staticmethod
    def parse_json(text: str | None) -> dict:
        try:
            return json.loads(text or "")
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text or "", re.S)   # tolerate code fences or stray prose (prompt mode)
            if match:
                return json.loads(match.group(0))
            raise

    def complete_json(self, model: ModelConfig, messages: list[dict], schema: dict, name: str) -> dict:
        data = self._post(self.build_body(model, messages, schema, name)).json()
        if "error" in data:
            raise ProviderError(str(data["error"].get("message", data["error"])))
        choice = data["choices"][0]
        if choice.get("finish_reason") not in ("stop", "end_turn"):
            raise ProviderError(f"The model stopped early ({choice.get('finish_reason')}); try again")
        try:
            return self.parse_json(choice["message"]["content"])
        except json.JSONDecodeError as e:
            raise ProviderError("The model returned malformed JSON; try again") from e

    def stream_text(self, model: ModelConfig, messages: list[dict]) -> Iterator[str]:
        with self._post(self.build_body(model, messages, stream=True), stream=True) as r:
            r.encoding = "utf-8"   # text/event-stream has no charset, and requests would assume Latin-1
            for raw in r.iter_lines(decode_unicode=True):
                if not raw or not raw.startswith("data: "):
                    continue   # blank keep-alives and ": PROCESSING" comments
                data = raw[len("data: "):]
                if data == "[DONE]":
                    break
                event = json.loads(data)
                if "error" in event:
                    raise ProviderError(str(event["error"].get("message", event["error"])))
                delta = (event.get("choices") or [{}])[0].get("delta", {}).get("content")
                if delta:
                    yield delta


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI's own API, which names the output cap max_completion_tokens."""

    kind = "openai"
    max_tokens_field = "max_completion_tokens"


class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter: reasoning as an object, and routing only to providers that honour the JSON schema."""

    kind = "openrouter"

    def reasoning_fields(self, effort: str) -> dict:
        return {"reasoning": {"effort": effort, "exclude": True}}

    def json_schema_fields(self) -> dict:
        return {"provider": {"require_parameters": True}}

    def headers(self) -> dict:
        return super().headers() | {"X-Title": "Dholpur House"}
