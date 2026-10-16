"""Maps a provider `kind` from models.toml to its class, and hands out one instance per configured provider."""

from __future__ import annotations

from app.errors import ConfigError
from app.llm.base import LLMProvider
from app.models_config import ProviderConfig

_classes: dict[str, type[LLMProvider]] = {}
_instances: dict[ProviderConfig, LLMProvider] = {}


def register(cls: type[LLMProvider]) -> type[LLMProvider]:
    """Make a provider class available under its `kind` (usable as a class decorator)."""
    _classes[cls.kind] = cls
    return cls


def kinds() -> set[str]:
    return set(_classes)


def provider_class(kind: str) -> type[LLMProvider] | None:
    return _classes.get(kind)


def provider_for(config: ProviderConfig) -> LLMProvider:
    if config.kind not in _classes:
        raise ConfigError(f"provider '{config.name}': unknown kind '{config.kind}' (known: {sorted(_classes)})")
    if config not in _instances:
        _instances[config] = _classes[config.kind](config)
    return _instances[config]


def _register_builtins() -> None:
    from app.llm.anthropic_provider import AnthropicProvider
    from app.llm.openai_compat import OpenAICompatibleProvider, OpenAIProvider, OpenRouterProvider

    for cls in (OpenAICompatibleProvider, OpenAIProvider, OpenRouterProvider, AnthropicProvider):
        register(cls)


_register_builtins()
