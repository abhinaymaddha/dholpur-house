"""Providers and named model slots (model_1, model_2, ...) from models.toml. Flows ask for a slot."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings

DEFAULT_FILE = Path(__file__).resolve().parents[1] / "models.toml"
KINDS = {"openrouter", "openai", "anthropic", "openai_compatible"}
JSON_MODES = {"schema", "object", "prompt"}


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Provider:
    name: str
    kind: str
    base_url: str | None = None
    api_key_env: str | None = None
    api_key: str | None = field(default=None, repr=False)

    def key(self) -> str:
        """The API key: inline `api_key` if set, else the environment variable named by `api_key_env`."""
        if self.api_key:
            return self.api_key
        value = os.environ.get(self.api_key_env or "", "")
        if not value:
            raise ConfigError(f"No API key for provider '{self.name}': set {self.api_key_env} in backend/.env "
                              f"(or api_key in models.toml)")
        return value


@dataclass(frozen=True)
class ModelConfig:
    key: str
    provider: Provider
    id: str
    max_tokens: int = 4000
    reasoning_effort: str | None = None
    temperature: float | None = None
    json_mode: str = "schema"
    fallbacks: str | None = None


_cache: dict = {"mtime": None, "models": {}}


def _path() -> Path:
    return Path(settings.models_file) if settings.models_file else DEFAULT_FILE


def _parse(raw: dict) -> dict[str, ModelConfig]:
    providers = {}
    for name, cfg in raw.get("providers", {}).items():
        if cfg.get("kind") not in KINDS:
            raise ConfigError(f"provider '{name}': kind must be one of {sorted(KINDS)}")
        if cfg["kind"] != "anthropic" and not cfg.get("base_url"):
            raise ConfigError(f"provider '{name}': base_url is required")
        providers[name] = Provider(name=name, **cfg)
    models = {}
    for key, cfg in raw.get("models", {}).items():
        cfg = dict(cfg)
        pname = cfg.pop("provider", None)
        if pname not in providers:
            raise ConfigError(f"model '{key}': provider '{pname}' is not defined under [providers]")
        if cfg.get("json_mode", "schema") not in JSON_MODES:
            raise ConfigError(f"model '{key}': json_mode must be one of {sorted(JSON_MODES)}")
        models[key] = ModelConfig(key=key, provider=providers[pname], **cfg)
    return models


def all_models() -> dict[str, ModelConfig]:
    """Parsed models.toml, re-read whenever the file changes."""
    path = _path()
    mtime = path.stat().st_mtime
    if _cache["mtime"] != mtime:
        _cache["models"] = _parse(tomllib.loads(path.read_text(encoding="utf-8")))
        _cache["mtime"] = mtime
    return _cache["models"]


def get_model(key: str) -> ModelConfig:
    models = all_models()
    if key not in models:
        raise ConfigError(f"{key} is not defined in {_path().name} (have: {', '.join(models)})")
    return models[key]
