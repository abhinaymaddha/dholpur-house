"""The provider interface every LLM backend implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from app.models_config import ModelConfig, ProviderConfig


class LLMProvider(ABC):
    """One configured provider (a [providers.*] entry in models.toml).

    Subclasses set `kind` (the value used in models.toml) and implement the two calls the app needs.
    Raise app.errors.ProviderError for failures the user should see.
    """

    kind: ClassVar[str]
    requires_base_url: ClassVar[bool] = True

    def __init__(self, config: ProviderConfig):
        self.config = config

    @property
    def name(self) -> str:
        return self.config.name

    @abstractmethod
    def complete_json(self, model: ModelConfig, messages: list[dict], schema: dict, name: str) -> dict:
        """One non-streamed call returning a JSON object that matches `schema`."""

    @abstractmethod
    def stream_text(self, model: ModelConfig, messages: list[dict]) -> Iterator[str]:
        """Stream plain-text deltas of the reply."""
