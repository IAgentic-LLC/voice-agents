"""Chapter 27: one correlation id, one timeline, built from
whatever this book's own tracing already wrote down.

Every event this book has ever logged already carries a room name,
Chapter 4's own choice for a call's id, so the two sides of a call
could be lined up afterwards. This chapter names that choice for
what it always was and builds one tool that reconstructs a whole
call from it.
"""

from voicelab import runlog


def timeline(stages_path: str, room: str) -> list[dict]:
    """Every event this run recorded for one call, in the order it
    happened, and nothing from any other call mixed in."""
    rows = [r for r in runlog.read(stages_path) if r.get("room") == room]
    return sorted(rows, key=lambda r: r["at"])


def biggest_gap(events: list[dict]) -> tuple[dict, dict, float]:
    """The two consecutive events with the longest gap between
    them. This looks at adjacency alone; it does not know which
    events are a matched start and end of the same real wait."""
    best = None
    for a, b in zip(events, events[1:]):
        gap = b["at"] - a["at"]
        if best is None or gap > best[2]:
            best = (a, b, gap)
    return best


def paired_duration(events: list[dict], start_event: str,
                    end_event: str) -> float | None:
    """How long a specific start/end pair actually took, matched by
    the event names that started and ended it, not by whichever gap
    in the raw timeline happens to be largest."""
    start = next((e for e in events if e["event"] == start_event), None)
    end = next((e for e in events if e["event"] == end_event), None)
    if start is None or end is None:
        return None
    return end["at"] - start["at"]
