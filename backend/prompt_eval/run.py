"""Run the prompt test cases and print the results for review.

    python -m prompt_eval.run evaluator        # each evaluator case (one LLM call each)
    python -m prompt_eval.run questions        # generated questions per case (one LLM call each)
    python -m prompt_eval.run evaluator ir_vague tone_partisan   # only some cases

Cases live next to this file as JSON; add more as you tune. Uses the models in models.toml.
"""

import json
import sys
from pathlib import Path

from app.database import pool
from app.dependencies import get_bank, get_interviews, get_question_sources
from app.interview import evaluator
from app.interview.session import Filters, InterviewSession

HERE = Path(__file__).parent


def run_evaluator(only: list[str]) -> None:
    for c in json.loads((HERE / "evaluator_cases.json").read_text()):
        if only and c["id"] not in only:
            continue
        exchange = f"Board: {c['question']}\nCandidate: {c['answer']}"
        pairs = [(r["text"], r["follow_up"]) for r in get_bank().similar([c["question"]], n=12) if r["follow_up"]][:5]
        e, follow_up = evaluator.evaluate(c["topic"], c["context"], c["reference"], exchange, c["answer"], 2, pairs)
        print(f"\n{'=' * 100}\n{c['id']}  (expect: {c['expect']})")
        print(f"verdict: {e['verdict']}  avg {e['average']}  {e['scores']}")
        for i in e["issues"]:
            print(f"  [{i['type']}] \"{i['quote']}\"\n      why: {i['why']}\n      fix: {i['fix']}")
        print(f"  strengths: {e['strengths']}")
        print(f"  critique: {e['critique']}")
        print(f"  missing: {e['missing_points']}")
        print(f"  model answer: {e['model_answer_points']}")
        print(f"  follow-up: {follow_up}")
        print(f"  guard removed: {e['guard']}")


def run_questions(only: list[str]) -> None:
    for c in json.loads((HERE / "question_cases.json").read_text()):
        if only and c["id"] not in only:
            continue
        print(f"\n{'=' * 100}\n{c['id']}  topics={c['topics']} board={c['board']} daf={'yes' if c['daf'] else 'no'}")
        session = InterviewSession.open(None, get_interviews(), get_bank(), get_question_sources())
        filters = Filters(topics=c["topics"], board=c["board"], daf=c["daf"])
        for _ in range(c["count"]):
            turn = session.next_question(filters)
            s = turn["source"]
            print(f"- [{s.get('target_angle')} -> {s['angle']}] {turn['question']}\n    builds on: {s['based_on']}"
                  f"{' | DAF item: ' + s['daf_item'] if s.get('daf_item') else ''}{' | article: ' + s['title'] if s.get('title') else ''}")


if __name__ == "__main__":
    pool.open()
    what, *only = sys.argv[1:] or ["evaluator"]
    {"evaluator": run_evaluator, "questions": run_questions}[what](only)
