"""Real past questions from the transcripts, searched by meaning (question embeddings).

Used three ways: as examples that ground generated questions, as questions asked directly in
"real questions only" mode, and as question -> follow-up pairs that show how boards follow up.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from app.ingest.tags import profile_tags
from app.repositories import QuestionRepository
from app.services.embeddings import embed

_STAGE_DIRECTION = re.compile(r"^\s*\([^)]{0,60}\)\s*")


def readable(text: str) -> str:
    """A past question as it can be read out: without a leading '(Then shifted to Polity)' note."""
    return _STAGE_DIRECTION.sub("", text).strip()


def fmt(rows: list[dict], with_follow_up: bool = True) -> str:
    lines = []
    for r in rows:
        lines.append(f"- {r['text']}  _(CSE {r['cse_year']}, {r['board']} board)_")
        if with_follow_up and r.get("follow_up"):
            lines.append(f"  - then: {r['follow_up']}")
    return "\n".join(lines) or "- (none found)"


def fmt_candidates(cands: list[dict]) -> str:
    blocks = []
    for c in cands:
        qs = "\n".join(f"  {q['member']}: {q['text']}" for q in c["questions"])
        blocks.append(f"### Candidate with DAF: {c['daf'] or 'n/a'} ({c['board']} board, CSE {c['cse_year']})\n{qs}")
    return "\n\n".join(blocks) or "(no close profile match)"


class QuestionBank:

    def __init__(self, repo: QuestionRepository, embedder: Callable[[list[str]], list] = embed):
        self.repo = repo
        self.embed = embedder

    def similar(self, queries: list[str], n: int = 12, board: str | None = None, exclude_ids: list[int] = (),
                exclude_transcript: str | None = None, askable: bool = False) -> list[dict]:
        """Past questions closest in meaning to any of the query texts, best first, de-duplicated.

        With a board, part of each query's results comes from that board so its style shows through.
        """
        if not queries:
            return []
        per_query = max(4, n // len(queries) + 2)
        found: dict[int, dict] = {}
        for vec in self.embed(queries):
            rows = []
            if board:
                rows += self.repo.nearest(vec, per_query // 2 + 1, board=board, exclude_ids=exclude_ids,
                                          exclude_transcript=exclude_transcript, askable=askable)
            rows += self.repo.nearest(vec, per_query, exclude_ids=exclude_ids,
                                      exclude_transcript=exclude_transcript, askable=askable)
            for r in rows:
                if r["id"] not in found or r["distance"] < found[r["id"]]["distance"]:
                    found[r["id"]] = r
        out, seen = [], set()
        for r in sorted(found.values(), key=lambda r: r["distance"]):   # drop near-identical wording
            key = r["text"].lower()[:60]
            if key not in seen:
                seen.add(key)
                out.append(r)
        return out[:n]

    def similar_candidates(self, daf: str, n: int = 2) -> list[dict]:
        """Transcripts of candidates whose profile best matches this DAF, with their questions in order."""
        profile = profile_tags(daf)
        if not any(profile.values()):
            return []
        return [{**c, "questions": self.repo.of_transcript(c["id"])}
                for c in self.repo.profile_matches(profile, n) if c["score"]]

    def board_examples(self, board: str, n: int = 8) -> list[dict]:
        return self.repo.board_sample(board, n)

    def topic_counts(self) -> dict[str, int]:
        return self.repo.topic_counts()
