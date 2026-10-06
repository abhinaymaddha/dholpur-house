"""units.jsonl -> data/extracted/<unit_id>.json via an LLM on OpenRouter.

pilot   : a handful of units through the sync API, to check quality and cost first.
submit  : everything not yet extracted, as one OpenRouter batch (50% price, 24h window).
collect : download batch results; failures are listed for `retry`.
retry   : re-run failed units through the sync API.
"""
from __future__ import annotations

import json
import random
import time
from concurrent.futures import ThreadPoolExecutor

from . import openrouter
from .common import DATA, EXTRACTED, UNITS, read_jsonl
from .prompt import SYSTEM, user_message
from .schema import TRANSCRIPT

DEFAULT_MODEL = "anthropic/claude-opus-5.5"
MAX_TOKENS = 32000
BATCH_STATE = DATA / "batch.json"
FAILED = DATA / "failed.json"
TERMINAL = {"completed", "failed", "expired", "cancelled"}


def _body(unit: dict, effort: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_message(unit)},
        ],
        "max_tokens": MAX_TOKENS,
        "reasoning": {"effort": effort},
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "upsc_transcript", "strict": True, "schema": TRANSCRIPT},
        },
    }


def _save(unit_id: str, resp: dict, effort: str) -> str:
    """Write the parsed result. Returns 'ok' or a failure reason."""
    choice = resp["choices"][0]
    if choice.get("finish_reason") not in ("stop", "end_turn"):
        return f"finish_reason={choice.get('finish_reason')}"
    try:
        data = json.loads(choice["message"]["content"])
    except (TypeError, json.JSONDecodeError) as e:
        return f"bad json: {e}"
    usage = resp.get("usage") or {}
    data["_meta"] = {
        "unit_id": unit_id, "model": resp.get("model"), "provider": resp.get("provider"), "effort": effort,
        "input_tokens": usage.get("prompt_tokens", 0), "output_tokens": usage.get("completion_tokens", 0),
        "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
        "cost_usd": usage.get("cost"),
    }
    EXTRACTED.mkdir(parents=True, exist_ok=True)
    (EXTRACTED / f"{unit_id}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return "ok"


def _pending(units: list[dict]) -> list[dict]:
    return [u for u in units if not (EXTRACTED / f"{u['unit_id']}.json").exists()]


def _extract_sync(unit: dict, model: str, effort: str) -> str:
    body = {"model": model, **_body(unit, effort),
            # only route to providers that honour response_format for this model
            "provider": {"require_parameters": True}}
    return _save(unit["unit_id"], openrouter.chat(body), effort)


def _run_sync(units: list[dict], model: str, effort: str, workers: int = 4) -> None:
    failed = {}
    with ThreadPoolExecutor(workers) as pool:
        futures = {u["unit_id"]: pool.submit(_extract_sync, u, model, effort) for u in units}
        for uid, fut in futures.items():
            try:
                status = fut.result()
            except (openrouter.OpenRouterError, KeyError) as e:
                status = f"{type(e).__name__}: {e}"
            print(f"  {uid}: {status}")
            if status != "ok":
                failed[uid] = status
    _record_failures(failed)


def _record_failures(failed: dict) -> None:
    FAILED.write_text(json.dumps(failed, indent=1))
    print(f"{len(failed)} failed -> {FAILED}" if failed else "no failures")


def pilot(n: int, model: str, effort: str, seed: int = 7) -> None:
    units = read_jsonl(UNITS)
    # Bias the sample toward hard cases: multi-part and Hindi-script transcripts.
    rng = random.Random(seed)
    hard = [u for u in units if len(u["message_ids"]) > 1 or any("ऀ" <= c <= "ॿ" for c in u["text"])]
    sample = rng.sample(hard, min(n // 2, len(hard)))
    rest = [u for u in units if u not in sample]
    sample += rng.sample(rest, n - len(sample))
    print(f"pilot: {len(sample)} units, model={model}, effort={effort}")
    _run_sync(sample, model, effort)
    usage_report([u["unit_id"] for u in sample])


def submit(model: str, effort: str, limit: int | None = None) -> None:
    pending = _pending(read_jsonl(UNITS))[:limit]
    if not pending:
        print("nothing pending")
        return
    batch = openrouter.create_batch(model, [{"custom_id": u["unit_id"], "body": _body(u, effort)} for u in pending])
    BATCH_STATE.write_text(json.dumps({"batch_id": batch["id"], "model": model, "effort": effort,
                                       "count": len(pending)}))
    print(f"submitted batch {batch['id']} ({batch['status']}) with {len(pending)} units")


def status() -> None:
    b = openrouter.get_batch(json.loads(BATCH_STATE.read_text())["batch_id"])
    print(b["status"], b["request_counts"], b.get("error") or "")


def collect(wait: bool = False) -> None:
    state = json.loads(BATCH_STATE.read_text())
    while True:
        b = openrouter.get_batch(state["batch_id"])
        if b["status"] in TERMINAL or not wait:
            break
        print(f"{b['status']}: {b['request_counts']}")
        time.sleep(120)
    if b["status"] != "completed":
        print(f"batch {b['status']}: {b['request_counts']} {b.get('error') or ''}")
        return
    failed, ok = {}, 0
    for r in b["results"]:
        resp = r.get("response")
        if resp and resp.get("status_code") == 200:
            status_ = _save(r["custom_id"], resp["body"], state["effort"])
        else:
            status_ = f"error: {r.get('error') or resp}"
        if status_ == "ok":
            ok += 1
        else:
            failed[r["custom_id"]] = status_
    print(f"saved {ok}; batch usage: {b.get('usage')}")
    _record_failures(failed)
    usage_report()


def retry(model: str, effort: str) -> None:
    ids = set(json.loads(FAILED.read_text()))
    units = [u for u in read_jsonl(UNITS) if u["unit_id"] in ids]
    print(f"retrying {len(units)} units")
    _run_sync(units, model, effort)


def usage_report(unit_ids: list[str] | None = None) -> None:
    files = [EXTRACTED / f"{i}.json" for i in unit_ids] if unit_ids else sorted(EXTRACTED.glob("*.json"))
    rows = [json.loads(f.read_text())["_meta"] for f in files if f.exists()]
    if not rows:
        return
    n = len(rows)
    inp = sum(r["input_tokens"] for r in rows)
    out = sum(r["output_tokens"] for r in rows)
    rsn = sum(r.get("reasoning_tokens") or 0 for r in rows)
    cost = sum(r.get("cost_usd") or 0 for r in rows)
    print(f"{n} extracted | input {inp:,} tok (avg {inp // n:,}) | output {out:,} tok (avg {out // n:,}, "
          f"reasoning {rsn:,}) | cost ${cost:.2f} (avg ${cost / n:.3f})")
