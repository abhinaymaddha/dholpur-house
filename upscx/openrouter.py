"""Minimal OpenRouter client: chat completions (sync) and the Batch API."""
from __future__ import annotations

import os
import time

import requests

BASE = "https://openrouter.ai/api/v1"
RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}


class OpenRouterError(RuntimeError):
    pass


def _headers() -> dict:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise OpenRouterError("OPENROUTER_API_KEY is not set (put it in .env)")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
            "X-Title": "upsc-transcripts"}


def _call(method: str, path: str, json_body: dict | None = None, timeout: int = 600, tries: int = 4) -> dict:
    for attempt in range(tries):
        try:
            r = requests.request(method, BASE + path, headers=_headers(), json=json_body, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout) as e:
            err = f"{type(e).__name__}: {e}"
        else:
            if r.status_code < 300:
                return r.json()
            err = f"HTTP {r.status_code}: {r.text[:500]}"
            if r.status_code not in RETRY_STATUS:
                raise OpenRouterError(err)
        time.sleep(2 ** attempt * 5)
    raise OpenRouterError(err)


def chat(body: dict) -> dict:
    data = _call("POST", "/chat/completions", body)
    if "error" in data:   # OpenRouter can return 200 with an error object mid-generation
        raise OpenRouterError(str(data["error"]))
    return data


def create_batch(model: str, requests_: list[dict], endpoint: str = "/v1/chat/completions") -> dict:
    # Key order matters: OpenRouter stream-parses the body and needs `requests` last.
    return _call("POST", "/batches", {"endpoint": endpoint, "model": model, "requests": requests_}, timeout=900)


def get_batch(batch_id: str) -> dict:
    return _call("GET", f"/batches/{batch_id}", timeout=900)
