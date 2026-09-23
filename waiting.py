"""Chapter 10: what the caller heard while the agent was working.

    uv run waiting.py runs/ch10-silent runs/ch10-filler
    uv run waiting.py --gone runs/ch10-hangup
    uv run waiting.py --trace runs/ch10-filler

For each run it reports how long the caller waited before hearing
anything, the longest silence they sat through, and how many bookings
reached the ledger. --gone asks the question that matters when a caller
leaves early: did the action happen anyway? --trace prints one call's
events in order. Times count from the end of the caller's question, as
everywhere in the book. Needs no key.
"""

import statistics
import sys

from voicelab import ledger, runlog


def calls_of(run: str) -> list[dict]:
    return runlog.read(f"{run}/trials.jsonl")


def traced(run: str, room: str, event: str) -> list[dict]:
    return [t for t in runlog.read(f"{run}/stages.jsonl")
            if t.get("stage") == "trace" and t["room"] == room
            and t["event"] == event]


def longest_quiet(call: dict) -> float:
    """The longest stretch with nothing to listen to.

    Before the agent says anything at all, that is the whole wait. After
    it starts, it is the largest gap in what it said.
    """
    gaps = [call["ttfa_s"]] if "ttfa_s" in call else []
    return max(gaps + call.get("quiet_s", []), default=0.0)


def main(runs: list[str]) -> None:
    print(f"{'run':<18}{'calls':>6}{'heard nothing for':>20}"
          f"{'longest silence':>18}{'booked':>8}")
    for run in runs:
        calls = calls_of(run)
        waits = [c["ttfa_s"] for c in calls if "ttfa_s" in c]
        quiet = [longest_quiet(c) for c in calls]
        booked = len(ledger.entries(f"{run}/ledger.jsonl"))
        first = f"{statistics.median(waits):.3f} s" if waits else "silence"
        print(f"{run.split('/')[-1]:<18}{len(calls):>6}{first:>20}"
              f"{statistics.median(quiet):>16.3f} s{booked:>8}")


def gone(run: str, only: int = 0) -> None:
    """What happened after the caller left, every call or just one."""
    rows = ledger.entries(f"{run}/ledger.jsonl")
    for n, call in enumerate(calls_of(run), 1):
        if only and n != only:
            continue
        t0 = call["speech_end_wall"]
        left = t0 + call.get("hung_up_after_s", 0)
        started = traced(run, call["room"], "tool called")
        done = traced(run, call["room"], "tool finished")
        mine = [r for r in rows if r.get("room") == call["room"]]
        print(f"call {n}: caller left {call.get('hung_up_after_s', 0):.1f} s"
              f" after the question")
        for t in started:
            print(f"  tool started  {t['at'] - t0:+.3f} s")
        for t in done:
            when = "after the caller left" if t["at"] > left else "in time"
            print(f"  tool finished {t['at'] - t0:+.3f} s  ({when})")
        print(f"  ledger: {len(mine)} booking(s) for a caller who is gone"
              if mine else "  ledger: nothing")


def trace(run: str) -> None:
    """One call's events in order, from the end of the caller's speech.

    `agent speaking` is when audio starts; `assistant said` is when the
    line has finished and been written to the history, which is why it
    comes later.
    """
    call = calls_of(run)[0]
    t0 = call["speech_end_wall"]
    events = ("user said", "tool called", "tool finished",
              "agent speaking", "assistant said")
    rows = [t for t in runlog.read(f"{run}/stages.jsonl")
            if t.get("stage") == "trace" and t["room"] == call["room"]
            and t["event"] in events]
    for t in sorted(rows, key=lambda t: t["at"]):
        text = (t.get("text") or "")[:44]
        print(f"{t['at'] - t0:+7.3f}  {t['event']:<16} {text}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--trace"]:
        trace(sys.argv[2])
    elif sys.argv[1:2] == ["--gone"]:
        rest = sys.argv[2:]
        pick = int(rest[rest.index("--call") + 1]) if "--call" in rest else 0
        gone(rest[0], pick)
    else:
        main(sys.argv[1:])
