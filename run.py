"""UPSC interview transcript extraction pipeline.

  python run.py parse <telegram-export-dir>
  python run.py segment
  python run.py pilot [--n 12] [--effort low] [--model anthropic/claude-opus-5.5]
  python run.py submit [--effort low] [--model ...] [--limit N]
  python run.py status
  python run.py collect [--wait]
  python run.py retry [--effort low] [--model ...]
  python run.py build
  python run.py audit [--n 50]
"""
import argparse
import os
from pathlib import Path

# OPENROUTER_API_KEY can live in a git-ignored .env next to this file.
env = Path(__file__).with_name(".env")
if env.exists():
    for line in env.read_text().splitlines():
        key, sep, val = line.partition("=")
        if sep and not key.strip().startswith("#"):
            os.environ.setdefault(key.strip(), val.strip().strip("'\""))

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("step", choices=["parse", "segment", "pilot", "submit", "status", "collect", "retry", "build", "audit"])
p.add_argument("path", nargs="?")
p.add_argument("--n", type=int)
p.add_argument("--effort", default="low", choices=["low", "medium", "high"])
p.add_argument("--model", default="anthropic/claude-opus-5.5", help="OpenRouter model slug")
p.add_argument("--limit", type=int)
p.add_argument("--wait", action="store_true")
a = p.parse_args()

if a.step == "parse":
    from upscx import parse
    parse.run(a.path)
elif a.step == "segment":
    from upscx import segment
    segment.run()
elif a.step == "build":
    from upscx import build
    build.run()
elif a.step == "audit":
    from upscx import audit
    audit.run(a.n or 50)
else:
    from upscx import extract
    if a.step == "pilot":
        extract.pilot(a.n or 12, a.model, a.effort)
    elif a.step == "submit":
        extract.submit(a.model, a.effort, a.limit)
    elif a.step == "status":
        extract.status()
    elif a.step == "collect":
        extract.collect(a.wait)
    elif a.step == "retry":
        extract.retry(a.model, a.effort)
