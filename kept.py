"""Chapter 12: what the agent knew at the start of a call, and what it said.

    uv run kept.py runs/ch12-calls-off runs/ch12-calls-on
    uv run kept.py --reconnect runs/ch12-drop runs/ch12-hold
    uv run kept.py --store runs/ch12-store/memory.jsonl

For each call it prints the line the agent's prompt began with, which is
everything it was told about this caller before they spoke, and the first
thing it said. --reconnect does the same for a call that dropped and came
back. --store prints the file itself. Needs no key.
"""

import sys

from voicelab import memory, runlog


def rows_of(run: str) -> list[dict]:
    return runlog.read(f"{run}/stages.jsonl")


def said_in(run: str, room: str) -> str:
    said = [r["text"] for r in rows_of(run)
            if r.get("stage") == "trace" and r.get("room") == room
            and r["event"] == "assistant said"]
    return said[0] if said else "(nothing)"


def knew_at(run: str) -> list[str]:
    return [r["known"] for r in rows_of(run)
            if r.get("stage") == "config" and r.get("known")]


def main(runs: list[str]) -> None:
    for run in runs:
        print(f"== {run.split('/')[-1]}")
        calls = runlog.read(f"{run}/trials.jsonl")
        knew = knew_at(run)
        for n, call in enumerate(calls, 1):
            print(f"  call {n}")
            if n <= len(knew):
                print(f"    knew:  {knew[n - 1]}")
            print(f"    said:  {said_in(run, call['room'])}")


def reconnect(runs: list[str]) -> None:
    """One call that dropped and came back, per run."""
    for run in runs:
        call = runlog.read(f"{run}/trials.jsonl")[0]
        print(f"== {run.split('/')[-1]}")
        print(f"  sessions started: {len(knew_at(run))}")
        for row in rows_of(run):
            if (row.get("stage") != "trace"
                    or row["event"] not in ("user said", "assistant said")):
                continue
            when = ("after rejoining" if row["at"] > call["rejoined_wall"]
                    else "before the drop")
            print(f"  {when:<16} {row['event']:<15}"
                  f"{(row.get('text') or '')[:42]}")


def store(path: str) -> None:
    kept = memory.recall(path, "caller")
    print(f"{len(kept)} fact(s) kept about this caller:")
    for fact, value in sorted(kept.items()):
        print(f"  {fact} = {value}")
    print(f"\nthe store allows only: {', '.join(memory.ALLOWED)}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--reconnect"]:
        reconnect(sys.argv[2:])
    elif sys.argv[1:2] == ["--store"]:
        store(sys.argv[2])
    else:
        main(sys.argv[1:])
