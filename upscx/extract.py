"""units.jsonl -> data/extracted/<unit_id>.json via Claude.

pilot   : a handful of units through the regular Messages API, to check quality and cost first.
submit  : everything not yet extracted, as one Message Batch (50% price, usually done within an hour).
collect : download batch results; refusals/errors are listed for `retry`.
retry   : re-run failed units synchronously (with server-side refusal fallback, which batches don't support).
"""
from __future__ import annotations

import json
import random
import time
from concurrent.futures import ThreadPoolExecutor

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from .common import DATA, EXTRACTED, UNITS, read_jsonl
from .prompt import SYSTEM, user_message
from .schema import TRANSCRIPT

MODEL = "claude-opus-5-5"
MAX_TOKENS = 32000
BATCH_STATE = DATA / "batch.json"
FAILED = DATA / "failed.json"


def _params(unit: dict, effort: str) -> dict:
    return {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": user_message(unit)}],
        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": TRANSCRIPT}},
    }


def _save(unit_id: str, msg, effort: str) -> dict | None:
    """Write the parsed result; return None (caller records a failure) unless it's clean JSON."""
    if msg.stop_reason != "end_turn":
        return None
    text = next(b.text for b in msg.content if b.type == "text")
    data = json.loads(text)
    data["_meta"] = {
        "unit_id": unit_id, "model": msg.model, "effort": effort,
        "input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens,
    }
    EXTRACTED.mkdir(parents=True, exist_ok=True)
    (EXTRACTED / f"{unit_id}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def _pending(units: list[dict]) -> list[dict]:
    return [u for u in units if not (EXTRACTED / f"{u['unit_id']}.json").exists()]


def _extract_sync(client: anthropic.Anthropic, unit: dict, effort: str) -> tuple[str, str]:
    with client.beta.messages.stream(
        **_params(unit, effort),
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        msg = stream.get_final_message()
    ok = _save(unit["unit_id"], msg, effort)
    return unit["unit_id"], ("ok" if ok else f"stop_reason={msg.stop_reason}")


def _run_sync(units: list[dict], effort: str, workers: int = 4) -> None:
    client = anthropic.Anthropic()
    failed = {}
    with ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(_extract_sync, client, u, effort): u["unit_id"] for u in units}
        for fut, uid in futures.items():
            try:
                uid, status = fut.result()
            except (anthropic.APIStatusError, anthropic.APIConnectionError, json.JSONDecodeError) as e:
                status = f"{type(e).__name__}: {e}"
            print(f"  {uid}: {status}")
            if status != "ok":
                failed[uid] = status
    _record_failures(failed)


def _record_failures(failed: dict) -> None:
    FAILED.write_text(json.dumps(failed, indent=1))
    print(f"{len(failed)} failed -> {FAILED}" if failed else "no failures")


def pilot(n: int, effort: str, seed: int = 7) -> None:
    units = read_jsonl(UNITS)
    # Bias the sample toward hard cases: multi-part, long, and Hindi-script transcripts.
    rng = random.Random(seed)
    hard = [u for u in units if len(u["message_ids"]) > 1 or any("ऀ" <= c <= "ॿ" for c in u["text"])]
    sample = rng.sample(hard, min(n // 2, len(hard)))
    rest = [u for u in units if u not in sample]
    sample += rng.sample(rest, n - len(sample))
    print(f"pilot: {len(sample)} units, effort={effort}")
    _run_sync(sample, effort)
    usage_report([u["unit_id"] for u in sample])


def submit(effort: str, limit: int | None = None) -> None:
    pending = _pending(read_jsonl(UNITS))[:limit]
    if not pending:
        print("nothing pending")
        return
    client = anthropic.Anthropic()
    batch = client.messages.batches.create(requests=[
        Request(custom_id=u["unit_id"], params=MessageCreateParamsNonStreaming(**_params(u, effort)))
        for u in pending
    ])
    BATCH_STATE.write_text(json.dumps({"batch_id": batch.id, "effort": effort, "count": len(pending)}))
    print(f"submitted batch {batch.id} with {len(pending)} units")


def status() -> None:
    state = json.loads(BATCH_STATE.read_text())
    b = anthropic.Anthropic().messages.batches.retrieve(state["batch_id"])
    print(b.processing_status, b.request_counts)


def collect(wait: bool = False) -> None:
    state = json.loads(BATCH_STATE.read_text())
    client = anthropic.Anthropic()
    while True:
        b = client.messages.batches.retrieve(state["batch_id"])
        if b.processing_status == "ended" or not wait:
            break
        print(f"{b.processing_status}: {b.request_counts}")
        time.sleep(60)
    if b.processing_status != "ended":
        print(f"batch still {b.processing_status}: {b.request_counts}")
        return
    failed, ok = {}, 0
    for r in client.messages.batches.results(state["batch_id"]):
        if r.result.type == "succeeded":
            try:
                saved = _save(r.custom_id, r.result.message, state["effort"])
            except json.JSONDecodeError as e:
                saved, failed[r.custom_id] = None, f"bad json: {e}"
            if saved:
                ok += 1
            else:
                failed.setdefault(r.custom_id, f"stop_reason={r.result.message.stop_reason}")
        else:
            failed[r.custom_id] = r.result.type
    print(f"saved {ok}")
    _record_failures(failed)
    usage_report()


def retry(effort: str) -> None:
    ids = set(json.loads(FAILED.read_text()))
    units = [u for u in read_jsonl(UNITS) if u["unit_id"] in ids]
    print(f"retrying {len(units)} units")
    _run_sync(units, effort)


def usage_report(unit_ids: list[str] | None = None) -> None:
    files = [EXTRACTED / f"{i}.json" for i in unit_ids] if unit_ids else sorted(EXTRACTED.glob("*.json"))
    rows = [json.loads(f.read_text())["_meta"] for f in files if f.exists()]
    if not rows:
        return
    inp = sum(r["input_tokens"] for r in rows)
    out = sum(r["output_tokens"] for r in rows)
    print(f"{len(rows)} extracted | input {inp:,} tok (avg {inp // len(rows):,}) | "
          f"output {out:,} tok (avg {out // len(rows):,}) incl. thinking")
