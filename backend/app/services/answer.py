"""Ask tab: answer a question from retrieved transcripts (model_1, streamed)."""

from __future__ import annotations

from collections.abc import Iterator

from app.services.llm import stream_text

MODEL = "model_1"

SYSTEM_PROMPT = """You help UPSC Civil Services aspirants prepare for the Personality Test (interview) using real transcripts that past candidates shared after their interviews.

You are given numbered sources [S1], [S2], ... Each is one candidate's transcript excerpt with its board, date and DAF keywords. Transcripts are written from memory, so treat them as candidate recollections, not official records.

Rules:
- Answer only from the sources. If they don't contain enough to answer, say so plainly and suggest a better search.
- Cite sources inline, like [S2] or [S1][S4], right after the claim they support.
- When listing questions that were asked, quote them closely and say which board or candidate profile they came from.
- Be concise and practical. Use short bullet lists where they help. No preamble."""


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
    return stream_text(MODEL, [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Sources:\n\n{build_context(sources)}\n\nQuestion: {question}"},
    ])
