"""Answer generation over retrieved transcripts, streamed from OpenRouter."""

from __future__ import annotations

import json
from collections.abc import Iterator

import requests

from app.config import settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """You help UPSC Civil Services aspirants prepare for the Personality Test (interview) using real transcripts that past candidates shared after their interviews.

You are given numbered sources [S1], [S2], ... Each is one candidate's transcript excerpt with its board, date and DAF keywords. Transcripts are written from memory, so treat them as candidate recollections, not official records.

Rules:
- Answer only from the sources. If they don't contain enough to answer, say so plainly and suggest a better search.
- Cite sources inline, like [S2] or [S1][S4], right after the claim they support.
- When listing questions that were asked, quote them closely and say which board or candidate profile they came from.
- Be concise and practical. Use short bullet lists where they help. No preamble."""


class LLMError(RuntimeError):
    pass


def build_context(sources: list[dict]) -> str:
    blocks = []
    for i, s in enumerate(sources, 1):
        head = (f"[S{i}] Board: {s['board']} | CSE {s['cse_year']} ({s['exam']}) | Interview date: "
                f"{s['interview_date'] or 'n/a'} | DAF: {s['daf'] or 'n/a'} | Optional: {s['optional_subject'] or 'n/a'}"
                + (f" | PT marks: {s['pt_marks']}" if s["pt_marks"] else ""))
        body = "\n...\n".join(e["text"] for e in s["excerpts"])
        blocks.append(f"{head}\n{body}")
    return "\n\n---\n\n".join(blocks)


def stream_answer(question: str, sources: list[dict]) -> Iterator[str]:
    if not settings.openrouter_api_key:
        raise LLMError("OPENROUTER_API_KEY is not configured on the server")
    body = {
        "model": settings.llm_model,
        "stream": True,
        "max_tokens": settings.llm_max_tokens,
        "reasoning": {"effort": "low", "exclude": True},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Sources:\n\n{build_context(sources)}\n\nQuestion: {question}"},
        ],
    }
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}", "X-Title": settings.app_name}
    with requests.post(OPENROUTER_URL, json=body, headers=headers, stream=True, timeout=(10, 300)) as r:
        if r.status_code != 200:
            raise LLMError(f"OpenRouter returned {r.status_code}: {r.text[:300]}")
        r.encoding = "utf-8"   # text/event-stream has no charset, and requests would assume Latin-1
        for raw in r.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data: "):
                continue   # blank keep-alives and ": OPENROUTER PROCESSING" comments
            data = raw[len("data: "):]
            if data == "[DONE]":
                break
            event = json.loads(data)
            if "error" in event:
                raise LLMError(str(event["error"].get("message", event["error"])))
            delta = (event.get("choices") or [{}])[0].get("delta", {}).get("content")
            if delta:
                yield delta
