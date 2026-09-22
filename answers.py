"""Chapter 11: what the agent said, and what it was working from.

    uv run answers.py runs/ch11-plain runs/ch11-spoken \n      runs/ch11-one
    uv run answers.py --said runs/ch11-plain

For each run it reports how many answers carried the fact the caller
asked for, how long the answers were, and how often a passage id ended
up in something a caller would have heard.

--said prints, for every call, what the transcriber heard, the query
the model chose to search with, the passages that came back and the
answer. Those four lines are the chapter: a wrong answer can come from
any of them. Needs no key.
"""

import re
import statistics
import sys

from voicelab import knowledge, runlog
from voicelab.policy import task_of

# A passage id said out loud. Most look like "refund-timing", and no
# caller has ever wanted one. The test has to be narrow: one id is the
# single word "cancelling", which is also how anyone would say the
# thing itself, so an id without a hyphen only counts inside brackets.
HYPHENATED = [p for p in knowledge.PASSAGES if "-" in p]
ID = re.compile("|".join(
    [rf"\b{re.escape(p)}\b" for p in HYPHENATED]
    + [rf"\[{re.escape(p)}\]" for p in knowledge.PASSAGES]
))


def spoken(run: str, room: str) -> str:
    return " ".join(
        t["text"] for t in runlog.read(f"{run}/stages.jsonl")
        if t.get("stage") == "trace" and t["room"] == room
        and t["event"] == "assistant said"
    )


def heard(run: str, room: str) -> str:
    """What the transcriber made of the caller, which is not always what
    the caller said."""
    return " ".join(
        t["text"] for t in runlog.read(f"{run}/stages.jsonl")
        if t.get("stage") == "trace" and t["room"] == room
        and t["event"] == "user said"
    )


def lookups(run: str, room: str) -> list[dict]:
    return [t for t in runlog.read(f"{run}/stages.jsonl")
            if t.get("stage") == "trace" and t["room"] == room
            and t["event"] == "looked up"]


def scored(run: str) -> list[dict]:
    out = []
    for call in runlog.read(f"{run}/trials.jsonl"):
        task = task_of(call.get("question", ""))
        if task is None:
            continue
        said = spoken(run, call["room"])
        found = lookups(run, call["room"])
        out.append({
            "task": task.name,
            "heard": heard(run, call["room"]),
            "queries": [f["text"] for f in found],
            "said": said,
            "right": task.passed(said),
            "words": len(said.split()),
            "leaked": bool(ID.search(said)),
            "passages": [p for f in found for p in f["passages"]],
            "searched": len(found),
        })
    return out


def main(runs: list[str]) -> None:
    print(f"{'run':<16}{'calls':>6}{'right':>9}{'words, median':>15}"
          f"{'longest':>9}{'id said aloud':>15}")
    for run in runs:
        rows = scored(run)
        if not rows:
            continue
        words = [r["words"] for r in rows]
        right = sum(r["right"] for r in rows)
        leaked = sum(r["leaked"] for r in rows)
        print(f"{run.split('/')[-1]:<16}{len(rows):>6}"
              f"{right:>6} of {len(rows)}{statistics.median(words):>15.0f}"
              f"{max(words):>9}{leaked:>12} of {len(rows)}")


def said(run: str) -> None:
    for row in scored(run):
        mark = "right" if row["right"] else "WRONG"
        flag = "  [id said aloud]" if row["leaked"] else ""
        print(f"[{mark}] {row['task']}, {row['words']} words{flag}")
        print(f"  heard:  {row['heard'] or '(nothing)'}")
        for query in row["queries"]:
            same = " (the caller's words)" if query == row["heard"] else ""
            print(f"  asked:  {query}{same}")
        print(f"  got:    {', '.join(row['passages']) or 'nothing'}")
        print(f"  said:   {row['said'] or '(nothing)'}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--said"]:
        said(sys.argv[2])
    else:
        main(sys.argv[1:])
