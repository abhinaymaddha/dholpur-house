import os

import pytest

from app import models_config
from app.errors import ConfigError
from app.models_config import ProviderConfig, all_models, get_model


@pytest.fixture
def toml(tmp_path, monkeypatch):
    path = tmp_path / "models.toml"
    monkeypatch.setattr(models_config.settings, "models_file", str(path))
    monkeypatch.setitem(models_config._cache, "mtime", None)

    def write(text):
        path.write_text(text)
        os.utime(path, (path.stat().st_mtime + 1,) * 2)   # a new mtime even within the same second
        return path
    yield write
    monkeypatch.setitem(models_config._cache, "mtime", None)


GOOD = """
[providers.or]
kind = "openrouter"
base_url = "https://openrouter.ai/api/v1"
api_key_env = "TEST_OR_KEY"

[providers.claude]
kind = "anthropic"
api_key_env = "TEST_CLAUDE_KEY"

[models.model_1]
provider = "or"
id = "a/b"
reasoning_effort = "low"

[models.model_2]
provider = "claude"
id = "claude-opus-5-5"
fallbacks = "default"
json_mode = "prompt"
"""


def test_parses_providers_and_models(toml):
    toml(GOOD)
    m = get_model("model_2")
    assert m.id == "claude-opus-5-5" and m.provider.kind == "anthropic" and m.fallbacks == "default"
    assert all_models()["model_1"].reasoning_effort == "low"


def test_reloads_when_the_file_changes(toml):
    toml(GOOD)
    assert get_model("model_1").id == "a/b"
    toml(GOOD.replace('id = "a/b"', 'id = "c/d"'))
    assert get_model("model_1").id == "c/d"


@pytest.mark.parametrize("text, match", [
    ('[providers.x]\nkind = "bogus"', "kind must be one of"),
    ('[providers.x]\nkind = "openai"', "base_url is required"),
    ('[providers.x]\nkind = "anthropic"\ncolour = "red"', "provider 'x'"),
    ('[models.model_1]\nprovider = "missing"\nid = "m"', "is not defined under"),
    (GOOD + '\n[models.model_3]\nprovider = "or"\nid = "m"\njson_mode = "xml"', "json_mode must be one of"),
    (GOOD + '\n[models.model_3]\nprovider = "or"\nid = "m"\nsize = 3', "model 'model_3'"),
])
def test_invalid_config(toml, text, match):
    toml(text)
    with pytest.raises(ConfigError, match=match):
        all_models()


def test_unknown_slot(toml):
    toml(GOOD)
    with pytest.raises(ConfigError, match="model_9 is not defined in models.toml"):
        get_model("model_9")


def test_api_key_resolution(monkeypatch):
    assert ProviderConfig(name="p", kind="openai", api_key="inline").key() == "inline"
    monkeypatch.setenv("TEST_KEY_VAR", "from-env")
    assert ProviderConfig(name="p", kind="openai", api_key_env="TEST_KEY_VAR").key() == "from-env"
    monkeypatch.delenv("TEST_KEY_VAR")
    with pytest.raises(ConfigError, match="set TEST_KEY_VAR in backend/.env"):
        ProviderConfig(name="p", kind="openai", api_key_env="TEST_KEY_VAR").key()
    assert "inline" not in repr(ProviderConfig(name="p", kind="openai", api_key="inline"))


def test_default_file_is_used_without_setting(monkeypatch):
    monkeypatch.setattr(models_config.settings, "models_file", None)
    assert models_config._path() == models_config.DEFAULT_FILE
