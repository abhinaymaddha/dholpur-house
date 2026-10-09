"""Named model slots (model_1, model_2, ...) loaded from models.toml. Flows ask for a slot, not a model id."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from app.config import settings

DEFAULT_FILE = Path(__file__).resolve().parents[1] / "models.toml"


@dataclass(frozen=True)
class ModelConfig:
    key: str
    id: str
    max_tokens: int = 4000
    reasoning_effort: str | None = None
    temperature: float | None = None


_cache: dict = {"mtime": None, "models": {}}


def _path() -> Path:
    return Path(settings.models_file) if settings.models_file else DEFAULT_FILE


def all_models() -> dict[str, ModelConfig]:
    """Parsed models.toml, re-read whenever the file changes."""
    path = _path()
    mtime = path.stat().st_mtime
    if _cache["mtime"] != mtime:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        _cache["models"] = {key: ModelConfig(key=key, **cfg) for key, cfg in raw.items()}
        _cache["mtime"] = mtime
    return _cache["models"]


def get_model(key: str) -> ModelConfig:
    models = all_models()
    if key not in models:
        raise KeyError(f"{key} is not defined in {_path().name} (have: {', '.join(models)})")
    return models[key]
