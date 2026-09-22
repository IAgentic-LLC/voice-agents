"""Chapter 9: a record of actions that must happen exactly once.

A voice agent's tools do things to the world. The world does not have an
undo button, and a caller who is asked "did that go through?" deserves an
answer that is not a guess. So every attempt to act is written down, and
the write is what decides whether the action happens.

An attempt carries a *key*: the same request, made twice, has the same
key. The first attempt with a key is committed; any later attempt with
that key is refused and returns what the first one did. That is all an
idempotency key is, and it belongs to the action, not to the framework.
"""

import json
from pathlib import Path

from voicelab import runlog


def attempt(path: str, key: str, action: str, **fields) -> dict:
    """Do this once. Returns the committed record, new or existing.

    The record says whether this call was the one that committed it, so a
    caller can tell "booked" from "already booked" without guessing.
    """
    for row in runlog.read(path):
        if row.get("key") == key:
            return {**row, "committed_now": False}
    row = {"key": key, "action": action, **fields}
    runlog.append(path, row)
    return {**row, "committed_now": True}


def entries(path: str, room: str | None = None) -> list[dict]:
    rows = runlog.read(path)
    return [r for r in rows if room is None or r.get("room") == room]


def summary(path: str) -> str:
    return json.dumps([
        {k: v for k, v in row.items() if k not in ("t", "key")}
        for row in runlog.read(path)
    ], indent=1)


def clear(path: str) -> None:
    Path(path).unlink(missing_ok=True)
