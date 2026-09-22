"""Chapter 9: what the agent actually did, per call.

    uv run actions.py runs/ch09-off-plain runs/ch09-off-split
    uv run actions.py --detail runs/ch09-off-split
    uv run actions.py --timing runs/ch09-off-split

For each run it reports how many times the tool was called, how many
bookings reached the ledger, and what was booked. One booking, for the
day the caller ended up asking for, is right wherever the caller agreed
to one; where nobody ever agreed, nothing booked is right. --detail
prints one call in full and --timing prints when each tool call
happened, so the score can be read rather than trusted. Needs no key.

"asked first" counts calls where the agent said something with a
question mark in it before acting. That is a crude test, and all these
runs need.
"""

import sys

from voicelab import ledger, runlog


def calls_of(run: str) -> list[dict]:
    return runlog.read(f"{run}/trials.jsonl")


def traced(run: str, room: str, events: tuple[str, ...]) -> list[dict]:
    return [t for t in runlog.read(f"{run}/stages.jsonl")
            if t.get("stage") == "trace" and t["room"] == room
            and t["event"] in events]


def asked_to_confirm(run: str, room: str) -> bool:
    said = traced(run, room, ("assistant said",))
    return any("?" in t.get("text", "") for t in said)


def report(run: str) -> dict:
    rows = ledger.entries(f"{run}/ledger.jsonl")
    out = {"calls": 0, "tool_calls": 0, "booked": 0, "days": set(),
           "asked": 0}
    for call in calls_of(run):
        room = call["room"]
        out["calls"] += 1
        out["tool_calls"] += len(traced(run, room, ("tool called",)))
        mine = [r for r in rows if r.get("room") == room]
        out["booked"] += len(mine)
        out["days"].update(r["day"].strip().lower() for r in mine)
        out["asked"] += asked_to_confirm(run, room)
    return out


def main(runs: list[str]) -> None:
    print(f"{'run':<18}{'calls':>6}{'tool calls':>12}{'booked':>8}"
          f"{'days booked':>22}{'asked first':>12}")
    for run in runs:
        got = report(run)
        days = ", ".join(sorted(got["days"])) or "none"
        print(f"{run.split('/')[-1]:<18}{got['calls']:>6}"
              f"{got['tool_calls']:>12}{got['booked']:>8}"
              f"{days:>22}{got['asked']:>7} of {got['calls']}")


def detail(run: str) -> None:
    call = calls_of(run)[0]
    room = call["room"]
    events = ("user said", "assistant said", "tool called")
    for t in sorted(traced(run, room, events), key=lambda t: t["t"]):
        print(f"{t['event']:<16} {t.get('text', '')}")
    rows = [r for r in ledger.entries(f"{run}/ledger.jsonl")
            if r.get("room") == room]
    print(f"\nledger: {len(rows)} booking(s)")
    for row in rows:
        print(f"  {row['day']} at {row['time_of_day']}")


def timing(run: str) -> None:
    """When each tool call happened, on the clocks the caller recorded.

    T0 is the end of the caller's speech, as everywhere else in the book.
    When the caller said something more (Chapter 7's --interrupt), the
    second column counts from the first loud frame of that.
    """
    print(f"{'call':>5}{'tool call, after T0':>22}{'after the reply':>18}")
    for n, call in enumerate(calls_of(run), 1):
        t0 = call["speech_end_wall"]
        reply = call.get("interrupt_start_wall")
        for t in traced(run, call["room"], ("tool called",)):
            since = f"{t['at'] - reply:+.3f} s" if reply else "-"
            print(f"{n:>5}{t['at'] - t0:>20.3f} s{since:>18}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--timing"]:
        timing(sys.argv[2])
    elif sys.argv[1:2] == ["--detail"]:
        detail(sys.argv[2])
    else:
        main(sys.argv[1:])
