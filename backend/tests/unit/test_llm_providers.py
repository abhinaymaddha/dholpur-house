import pytest

from app.models_config import ConfigError, _parse
from app.services import llm_anthropic, llm_openai

SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"], "additionalProperties": False}
MSGS = [{"role": "system", "content": "Be strict."}, {"role": "user", "content": "Rate this."}]


def models(slot: dict, provider: dict):
    return _parse({"providers": {"p": provider}, "models": {"model_1": {"provider": "p", **slot}}})["model_1"]


def test_openrouter_body():
    m = models({"id": "x/y", "reasoning_effort": "low"}, {"kind": "openrouter", "base_url": "https://openrouter.ai/api/v1"})
    body = llm_openai.build_body(m, MSGS, SCHEMA, "result")
    assert body["max_tokens"] == 4000 and body["reasoning"] == {"effort": "low", "exclude": True}
    assert body["response_format"]["json_schema"]["schema"] == SCHEMA and body["provider"] == {"require_parameters": True}


def test_openai_body_uses_openai_parameter_names():
    m = models({"id": "gpt-5.5", "reasoning_effort": "low"}, {"kind": "openai", "base_url": "https://api.openai.com/v1"})
    body = llm_openai.build_body(m, MSGS, SCHEMA, "result")
    assert body["max_completion_tokens"] == 4000 and body["reasoning_effort"] == "low"
    assert "reasoning" not in body and "provider" not in body


def test_json_object_mode_puts_schema_in_prompt():
    m = models({"id": "llama3.1", "json_mode": "object"}, {"kind": "openai_compatible", "base_url": "http://localhost:11434/v1"})
    body = llm_openai.build_body(m, MSGS, SCHEMA, "result")
    assert body["response_format"] == {"type": "json_object"} and '"a"' in body["messages"][-1]["content"]
    assert MSGS[-1]["content"] == "Rate this."   # caller's messages untouched


def test_anthropic_params():
    m = models({"id": "claude-opus-5-5", "reasoning_effort": "medium", "fallbacks": "default"}, {"kind": "anthropic"})
    p = llm_anthropic.build_params(m, MSGS, SCHEMA)
    assert p["system"] == "Be strict." and p["messages"] == [MSGS[1]]
    assert p["output_config"] == {"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}}
    assert p["fallbacks"] == "default" and p["betas"] == [llm_anthropic.FALLBACK_BETA]
    assert "temperature" not in p


def test_config_errors():
    with pytest.raises(ConfigError):
        _parse({"providers": {"p": {"kind": "nope", "base_url": "x"}}, "models": {}})
    with pytest.raises(ConfigError):
        _parse({"providers": {}, "models": {"model_1": {"provider": "missing", "id": "x"}}})


def test_missing_key_is_a_clear_error(monkeypatch):
    m = models({"id": "x"}, {"kind": "openai", "base_url": "https://api.openai.com/v1", "api_key_env": "NO_SUCH_KEY_VAR"})
    monkeypatch.delenv("NO_SUCH_KEY_VAR", raising=False)
    with pytest.raises(ConfigError, match="NO_SUCH_KEY_VAR"):
        m.provider.key()
