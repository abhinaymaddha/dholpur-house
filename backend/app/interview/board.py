"""A full interview: the board, not the candidate, decides what to ask, in the order real boards do.

The Chairperson opens with the candidate's background, the four members each take an area, and the
Chairperson closes with a situational or ethics question. Within an area, topics are drawn about as
often as real boards asked them (the number of past questions on each), so a full interview often
touches the economy and rarely sports. The plan is seeded by the session, so it stays the same
across requests, and only changes if the candidate changes the length or adds their DAF.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

DAF = "DAF & Background"
CHAIR = "Chairperson"
OPENING = [DAF, "Motivation & Personal"]
CLOSING = ["Situational / Hypothetical", "Ethics & Values"]
MEMBER_AREAS = {
    "Member 1": ["History & Culture", "Geography", "Science & Technology", "Education", "Health", "Sports",
                 "Agriculture & Rural"],                                             # background and interests
    "Member 2": ["International Relations", "Security & Defence", "Economy"],        # current affairs
    "Member 3": ["Polity & Constitution", "Governance & Administration", "Society & Social Justice"],
    "Member 4": ["Economy", "Environment & Disasters", "Agriculture & Rural", "Science & Technology",
                 "Ethics & Values"],
}


@dataclass(frozen=True)
class Slot:
    member: str
    topic: str


def plan(length: int, seed: str, weights: dict[str, int], has_daf: bool) -> list[Slot]:
    """The main questions of a full interview, in order: who asks, and on which topic."""
    rng = random.Random(seed)
    opening = max(1, round(length * 0.2))
    middle = length - opening - 1
    opening_topics = OPENING if has_daf else OPENING[1:]
    slots = [Slot(CHAIR, opening_topics[i % len(opening_topics)]) for i in range(opening)]
    for i, (member, area) in enumerate(MEMBER_AREAS.items()):
        pool = [*area, DAF] if has_daf and member == "Member 1" else area   # Member 1 also asks about the DAF
        last = None
        for _ in range(middle // 4 + (1 if i < middle % 4 else 0)):
            choices = [t for t in pool if t != last]
            last = rng.choices(choices, weights=[weights.get(t, 0) + 1 for t in choices])[0]
            slots.append(Slot(member, last))
    slots.append(Slot(CHAIR, rng.choice(CLOSING)))
    return slots
