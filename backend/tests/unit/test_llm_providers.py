"""LLM providers: request shapes per provider, response parsing and error translation, with HTTP and the
Anthropic SDK replaced by fakes."""

import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest
import requests

from app import llm
from app.errors import ConfigError, ProviderError
from app.llm import registry
from app.llm.anthropic_provider import FALLBACK_BETA, AnthropicProvider
from app.llm.openai_compat import OpenAICompatibleProvider, OpenAIProvider, OpenRouterProvider
from app.models_config import ModelConfig, ProviderConfig

SCHEMA = {"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"]}
MSGS = [{"role": "system", "content": "Be brief."}, {"role": "user", "content": "Hi"}]


def provider(cls, **kw):
    cfg = ProviderConfig(name=cls.kind, kind=cls.kind, base_url=kw.pop("base_url", "https://api.test/v1/"),
                         api_key=kw.pop("api_key", "k"), **kw)
    return cls(cfg)


def model(p, **kw):
    return ModelConfig(key="model_x", provider=p.config, id="m-1", **kw)


class FakeResponse:
    def __init__(self, status=200, payload=None, lines=(), text=""):
        self.status_code, self._payload, self._lines, self.text = status, payload, lines, text
        self.encoding = None

    def json(self):
        return self._payload

    def iter_lines(self, decode_unicode=False):
        yield from self._lines

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def post(monkeypatch):
    calls = []

    def install(response):
        def fake(url, json, headers, stream, timeout):
            calls.append({"url": url, "json": json, "headers": headers, "stream": stream})
            if isinstance(response, Exception):
                raise response
            return response
        monkeypatch.setattr(requests, "post", fake)
        return calls
    return install


def ok(content, finish="stop"):
    return FakeResponse(payload={"choices": [{"message": {"content": content}, "finish_reason": finish}]})


# ---------- OpenAI-compatible family ----------

def test_body_with_schema_reasoning_and_temperature():
    p = provider(OpenAICompatibleProvider)
    body = p.build_body(model(p, reasoning_effort="low", temperature=0.2), MSGS, SCHEMA, "thing")
    assert body["max_tokens"] == 4000 and body["reasoning_effort"] == "low" and body["temperature"] == 0.2
    assert body["response_format"]["json_schema"] == {"name": "thing", "strict": True, "schema": SCHEMA}
    assert "stream" not in body and body["messages"] == MSGS


def test_prompt_and_object_json_modes_put_the_schema_in_the_prompt():
    p = provider(OpenAICompatibleProvider)
    body = p.build_body(model(p, json_mode="prompt"), MSGS, SCHEMA)
    assert "response_format" not in body and json.dumps(SCHEMA) in body["messages"][-1]["content"]
    assert MSGS[-1]["content"] == "Hi"   # the caller's messages are not modified
    body = p.build_body(model(p, json_mode="object"), MSGS, SCHEMA)
    assert body["response_format"] == {"type": "json_object"}


def test_openai_and_openrouter_differences():
    o = provider(OpenAIProvider)
    assert "max_completion_tokens" in o.build_body(model(o), MSGS)
    r = provider(OpenRouterProvider)
    body = r.build_body(model(r, reasoning_effort="medium"), MSGS, SCHEMA, stream=True)
    assert body["reasoning"] == {"effort": "medium", "exclude": True}
    assert body["provider"] == {"require_parameters": True} and body["stream"] is True
    assert r.headers() == {"Authorization": "Bearer k", "X-Title": "Dholpur House"}


def test_complete_json_posts_and_parses(post):
    calls = post(ok('{"a": 1}'))
    p = provider(OpenRouterProvider)
    assert p.complete_json(model(p), MSGS, SCHEMA, "x") == {"a": 1}
    assert calls[0]["url"] == "https://api.test/v1/chat/completions"
    assert calls[0]["headers"]["Authorization"] == "Bearer k"


def test_complete_json_tolerates_code_fences(post):
    post(ok('Sure:\n```json\n{"a": 2}\n```'))
    p = provider(OpenAICompatibleProvider)
    assert p.complete_json(model(p, json_mode="prompt"), MSGS, SCHEMA, "x") == {"a": 2}


@pytest.mark.parametrize("response, message", [
    (ok("not json at all"), "malformed JSON"),
    (ok('{"a": 1}', finish="length"), "stopped early"),
    (FakeResponse(payload={"error": {"message": "quota"}}), "quota"),
    (FakeResponse(status=429, text="slow down"), "returned 429: slow down"),
    (requests.ConnectionError("dns"), "Could not reach"),
])
def test_complete_json_errors(post, response, message):
    post(response)
    p = provider(OpenAICompatibleProvider)
    with pytest.raises(ProviderError, match=message):
        p.complete_json(model(p), MSGS, SCHEMA, "x")


def test_stream_text_yields_deltas_until_done(post):
    lines = ["", ": PROCESSING", 'data: {"choices": [{"delta": {"content": "Hel"}}]}',
             'data: {"choices": [{"delta": {}}]}', 'data: {"choices": [{"delta": {"content": "lo ✓"}}]}',
             "data: [DONE]", 'data: {"choices": [{"delta": {"content": "ignored"}}]}']
    calls = post(FakeResponse(lines=lines))
    p = provider(OpenAICompatibleProvider)
    assert "".join(p.stream_text(model(p), MSGS)) == "Hello ✓"
    assert calls[0]["stream"] is True and calls[0]["json"]["stream"] is True


def test_stream_text_error_event(post):
    post(FakeResponse(lines=['data: {"error": {"message": "overloaded"}}']))
    p = provider(OpenAICompatibleProvider)
    with pytest.raises(ProviderError, match="overloaded"):
        list(p.stream_text(model(p), MSGS))


# ---------- Anthropic ----------

def message(text='{"a": 1}', stop="end_turn", details=None):
    return SimpleNamespace(content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=text)],
                           stop_reason=stop, stop_details=details)


class FakeStream:
    def __init__(self, deltas, final):
        self.text_stream, self._final = iter(deltas), final

    def get_final_message(self):
        return self._final

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeMessages:
    def __init__(self, result=None, stream=None, error=None):
        self.result, self._stream, self.error, self.calls = result, stream, error, []

    def create(self, **params):
        self.calls.append(params)
        if self.error:
            raise self.error
        return self.result

    def stream(self, **params):
        self.calls.append(params)
        if self.error:
            raise self.error
        return self._stream


def claude(messages_api):
    p = provider(AnthropicProvider, base_url=None)
    p.__dict__["client"] = SimpleNamespace(messages=messages_api, beta=SimpleNamespace(messages=messages_api))
    return p


def test_anthropic_params():
    p = provider(AnthropicProvider, base_url=None)
    params = p.build_params(model(p, reasoning_effort="high", temperature=0.5, fallbacks="default"), MSGS, SCHEMA)
    assert params["system"] == "Be brief." and params["messages"] == [MSGS[1]]
    assert params["output_config"] == {"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}}
    assert params["temperature"] == 0.5 and params["betas"] == [FALLBACK_BETA] and params["fallbacks"] == "default"
    plain = p.build_params(model(p), [MSGS[1]])
    assert set(plain) == {"model", "max_tokens", "messages"}


def test_anthropic_complete_json_uses_beta_only_with_fallbacks():
    api = FakeMessages(result=message())
    p = claude(api)
    assert p.complete_json(model(p), MSGS, SCHEMA, "x") == {"a": 1}
    assert p._api({"betas": []}) is p.client.beta.messages and p._api({}) is p.client.messages


@pytest.mark.parametrize("result, match", [
    (message(stop="refusal", details=SimpleNamespace(category="cyber")), r"declined this request \(cyber\)"),
    (message(stop="refusal"), "declined this request$"),
    (message(stop="max_tokens"), "max_tokens"),
    (message(text="{oops"), "malformed JSON"),
])
def test_anthropic_complete_json_problems(result, match):
    p = claude(FakeMessages(result=result))
    with pytest.raises(ProviderError, match=match):
        p.complete_json(model(p), MSGS, SCHEMA, "x")


REQ = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.mark.parametrize("error, match", [
    (anthropic.RateLimitError("rate", response=httpx.Response(429, request=REQ), body=None), "rate limit"),
    (anthropic.InternalServerError("boom", response=httpx.Response(500, request=REQ), body=None), "returned 500: boom"),
    (anthropic.APIConnectionError(request=REQ), "Could not reach the Claude API"),
])
def test_anthropic_errors_are_translated(error, match):
    p = claude(FakeMessages(error=error))
    with pytest.raises(ProviderError, match=match):
        p.complete_json(model(p), MSGS, SCHEMA, "x")
    with pytest.raises(ProviderError, match=match):
        list(p.stream_text(model(p), MSGS))


def test_anthropic_stream():
    p = claude(FakeMessages(stream=FakeStream(["Na", "maste"], message())))
    assert "".join(p.stream_text(model(p), MSGS)) == "Namaste"
    p = claude(FakeMessages(stream=FakeStream(["cut"], message(stop="max_tokens"))))
    with pytest.raises(ProviderError, match="max_tokens"):
        list(p.stream_text(model(p), MSGS))


def test_anthropic_client_construction():
    assert isinstance(provider(AnthropicProvider, base_url=None).client, anthropic.Anthropic)
    proxied = provider(AnthropicProvider, base_url="https://proxy.test").client
    assert str(proxied.base_url).startswith("https://proxy.test")


# ---------- registry and facade ----------

def test_registry_knows_builtins_and_caches_instances():
    assert {"openai_compatible", "openai", "openrouter", "anthropic", "fake"} <= registry.kinds()
    cfg = ProviderConfig(name="x", kind="openai", base_url="https://x", api_key="k")
    assert registry.provider_for(cfg) is registry.provider_for(cfg)
    assert registry.provider_class("nope") is None
    with pytest.raises(ConfigError, match="unknown kind"):
        registry.provider_for(ProviderConfig(name="y", kind="nope"))


def test_facade_routes_to_the_slot_provider(fake_llm):
    fake_llm.json["thing"] = lambda messages: {"ok": messages[0]["content"]}
    assert llm.complete_json("model_2", [{"role": "user", "content": "q"}], SCHEMA, "thing") == {"ok": "q"}
    assert "".join(llm.stream_text("model_1", MSGS)) == "An answer citing [S1]."
    assert [c["model"] for c in fake_llm.calls] == ["model_2", "model_1"]
