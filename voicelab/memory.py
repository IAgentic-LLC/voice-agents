"""Chapter 12: what the agent is allowed to remember between calls.

A call's own history lives in the session and dies with it. Anything
that should outlast the call has to be written somewhere, and then it is
a record about a person rather than a message in a conversation. That is
a different kind of thing, with different rules, so this module keeps it
small and explicit: a few named facts per caller, each one written on
purpose.

Nothing here is a transcript. Storing the whole conversation is the easy
thing to build and the hard thing to defend, because a caller who reads
out a card number has now had it filed under their name.
"""

import time

from voicelab import runlog

# What an agent is allowed to keep. Anything else it learns is forgotten
# when the call ends, which is the point.
ALLOWED = ("name", "callback_day", "callback_time")


def remember(path: str, caller: str, fact: str, value: str) -> str:
    """Write one named fact about one caller. Refuses anything else."""
    if fact not in ALLOWED:
        return (f"I am not allowed to keep {fact!r}. "
                f"Only {', '.join(ALLOWED)}.")
    runlog.append(path, {"caller": caller, "fact": fact, "value": value,
                         "at": round(time.time(), 3)})
    return f"Noted {fact} for next time."


def recall(path: str, caller: str) -> dict[str, str]:
    """Everything kept about one caller, latest value of each fact."""
    out: dict[str, str] = {}
    for row in runlog.read(path):
        if row.get("caller") == caller and row.get("fact") in ALLOWED:
            out[row["fact"]] = row["value"]
    return out


def describe(path: str, caller: str) -> str:
    """What to put in the prompt at the start of a call."""
    known = recall(path, caller)
    if not known:
        return "You have not spoken to this caller before."
    facts = ", ".join(f"{k} is {v}" for k, v in sorted(known.items()))
    return f"You have spoken to this caller before. You know: {facts}."
