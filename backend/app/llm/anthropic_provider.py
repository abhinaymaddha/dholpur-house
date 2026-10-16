"""Anthropic's Claude API, through the official `anthropic` SDK."""

from __future__ import annotations

import json
from collections.abc import Iterator
from functools import cached_property

import anthropic

from app.errors import ProviderError
from app.llm.base import LLMProvider
from app.models_config import ModelConfig

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider(LLMProvider):
    kind = "anthropic"
    requires_base_url = False   # the SDK knows the endpoint; base_url only to route through a proxy

    @cached_property
    def client(self) -> anthropic.Anthropic:
        if self.config.base_url:
            return anthropic.Anthropic(api_key=self.config.key(), base_url=self.config.base_url)
        return anthropic.Anthropic(api_key=self.config.key())

    @staticmethod
    def build_params(model: ModelConfig, messages: list[dict], schema: dict | None = None) -> dict:
        """Messages API parameters. System messages move to `system`; the schema goes in output_config.format."""
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        params: dict = {"model": model.id, "max_tokens": model.max_tokens,
                        "messages": [m for m in messages if m["role"] != "system"]}
        if system:
            params["system"] = system
        output_config: dict = {}
        if model.reasoning_effort:
            output_config["effort"] = model.reasoning_effort
        if schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        if output_config:
            params["output_config"] = output_config
        if model.temperature is not None:
            params["temperature"] = model.temperature
        if model.fallbacks:
            params |= {"betas": [FALLBACK_BETA], "fallbacks": model.fallbacks}
        return params

    def _api(self, params: dict):
        return self.client.beta.messages if "betas" in params else self.client.messages

    @staticmethod
    def _check(message) -> None:
        if message.stop_reason == "refusal":
            category = getattr(message.stop_details, "category", None) if message.stop_details else None
            raise ProviderError(f"Claude declined this request{f' ({category})' if category else ''}")
        if message.stop_reason == "max_tokens":
            raise ProviderError("The model stopped early (max_tokens); try again or raise max_tokens")

    @staticmethod
    def _translate(e: Exception) -> ProviderError:
        if isinstance(e, anthropic.RateLimitError):
            return ProviderError("Claude API rate limit reached; try again shortly")
        if isinstance(e, anthropic.APIStatusError):
            return ProviderError(f"Claude API returned {e.status_code}: {e.message}")
        return ProviderError(f"Could not reach the Claude API: {e}")

    def complete_json(self, model: ModelConfig, messages: list[dict], schema: dict, name: str) -> dict:
        params = self.build_params(model, messages, schema)
        try:
            message = self._api(params).create(**params)
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
            raise self._translate(e) from e
        self._check(message)
        text = next((b.text for b in message.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ProviderError("The model returned malformed JSON; try again") from e

    def stream_text(self, model: ModelConfig, messages: list[dict]) -> Iterator[str]:
        params = self.build_params(model, messages)
        try:
            with self._api(params).stream(**params) as stream:
                yield from stream.text_stream
                self._check(stream.get_final_message())
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
            raise self._translate(e) from e
