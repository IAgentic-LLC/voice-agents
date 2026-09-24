"""Chapter 24: whether a benchmark's own scorer agrees with a human,
on answers a human labels before the scorer's own verdict is read.

Every probe here is a real string, run through the exact function
Chapters 8 and 11 both trust, `Task.passed`. `human_says_right` is a
judgment made about the answer's meaning, not about whether it
happens to contain the words the pattern looks for.
"""

from dataclasses import dataclass

from voicelab.policy import TASKS_BY_NAME


@dataclass(frozen=True)
class Probe:
    task: str
    answer: str
    human_says_right: bool
    note: str


PROBES = [
    Probe(
        "refund",
        "Sorry, refunds are NOT available within 5 to 10 minutes, "
        "please wait longer.",
        False,
        "negates the real policy and gives the wrong unit, but the "
        "number pattern still matches",
    ),
    Probe(
        "return",
        "No returns are accepted; that 30 day window already closed.",
        False,
        "states the opposite of the policy while still saying 30",
    ),
    Probe(
        "address",
        "Once it's shipped, that ship has sailed, I'm afraid.",
        True,
        "correct in meaning, phrased idiomatically with none of the "
        "listed keywords",
    ),
    Probe(
        "cancel",
        "No exceptions, this fee is mandatory for early cancellation.",
        False,
        "says a fee is charged, but opens with the word the pattern "
        "looks for",
    ),
    Probe(
        "hours",
        "We shut the doors at six in the evening on Saturdays.",
        True,
        "correct time, said in words instead of the digit-plus-pm "
        "form the pattern expects",
    ),
]


def scorer_verdict(probe: Probe) -> bool:
    return TASKS_BY_NAME[probe.task].passed(probe.answer)


def disagreements() -> list[Probe]:
    return [p for p in PROBES if scorer_verdict(p) != p.human_says_right]
