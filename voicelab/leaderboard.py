"""Chapter 26: a leaderboard that refuses to answer a question its
own data cannot support, instead of picking a winner and hiding
that the choice was arbitrary.

A candidate that violates any of Chapter 25's invariants is
disqualified before it is ever scored; a violation is not a data
point to average against everything else the candidate did right.
A candidate that clears the gate still only gets a winner's name if
every reasonable weighting from Chapter 22 agrees on the same one.
"""

from dataclasses import dataclass

from voicelab.invariants import (
    every_refund_matches_its_real_order,
    no_passage_id_spoken_aloud,
    no_run_exceeds_the_handoff_cap,
)
from voicelab.profile import Profile, one_score

WEIGHTINGS = [
    ("speed-weighted", 0.5, 0.2),
    ("cost-weighted", 0.1, 0.7),
]


@dataclass(frozen=True)
class Candidate:
    name: str
    run: str


def violation_count(candidate: Candidate) -> int:
    ids = no_passage_id_spoken_aloud(f"{candidate.run}/stages.jsonl")
    refunds = every_refund_matches_its_real_order(
        f"{candidate.run}/ledger.jsonl"
    )
    bounces = no_run_exceeds_the_handoff_cap(f"{candidate.run}/stages.jsonl")
    return len(ids) + len(refunds) + len(bounces)


def stable_winner(profiles: list[Profile]) -> str | None:
    """The run name every weighting in WEIGHTINGS agrees is best, or
    None if the ranking flips depending on which one is used."""
    max_wait = max(p.ttfa_median_s for p in profiles)
    max_cost = max(p.cost_per_call for p in profiles)
    winners = set()
    for _, weight_speed, weight_cost in WEIGHTINGS:
        scores = {
            p.run: one_score(p, weight_speed=weight_speed,
                             weight_cost=weight_cost,
                             max_wait_s=max_wait, max_cost=max_cost)
            for p in profiles
        }
        winners.add(max(scores, key=scores.get))
    return winners.pop() if len(winners) == 1 else None
