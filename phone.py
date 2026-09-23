"""Chapter 14: what a phone leg costs, and what it carries.

    uv run phone.py runs/ch14-phone runs/ch14-room
    uv run phone.py --keys runs/ch14-phone
    uv run phone.py --facts runs/ch14-phone --call 1

The two runs are the same agent answering the same question. One
arrives over a SIP trunk as G.711 at 8 kHz; the other joins the room
directly, as every caller since Chapter 3 has. Both are traced by the
same code, so the stages line up.

--keys prints what the keypad sent, which on a phone leg arrives as a
named event rather than as a sound. --facts prints what the signalling
said about the caller. Needs no key.
"""

import statistics
import sys

from voicelab import runlog, stats

# The stages both legs record, in order.
FROM, TO = "user listening", "first speech byte"


def calls_in(run: str) -> list[dict]:
    """Group a run's trace rows by call."""
    rows = runlog.read(f"{run}/stages.jsonl")
    order, seen = [], {}
    for row in rows:
        room = row.get("room")
        if not room:
            continue
        if room not in seen:
            seen[room] = []
            order.append(room)
        seen[room].append(row)
    return [seen[room] for room in order]


def gap(call: list[dict], start: str, end: str) -> float | None:
    """Seconds between two traced events in one call."""
    at = {}
    for row in call:
        if row.get("stage") == "trace" and row["event"] in (start, end):
            at.setdefault(row["event"], row["at"])
    if start in at and end in at and at[end] > at[start]:
        return at[end] - at[start]
    return None


def heard_in(call: list[dict]) -> str:
    said = [r["text"] for r in call
            if r.get("event") == "user said" and r.get("text")]
    return said[0] if said else ""


def main(runs: list[str]) -> None:
    print(f"{'run':<16}{'calls':>6}{'transcribed':>13}"
          f"{'answered in, median':>21}")
    for run in runs:
        calls = calls_in(run)
        waits = [w for w in (gap(c, FROM, TO) for c in calls) if w]
        exact = sum(heard_in(c).rstrip(".") ==
                    "Please book me a callback for Thursday at 2:00 p.m"
                    for c in calls)
        wait = f"{statistics.median(waits):.3f} s" if waits else "-"
        print(f"{run.split('/')[-1]:<16}{len(calls):>6}"
              f"{exact:>7} of {len(calls)}{wait:>21}")
    if len(runs) == 2:
        a = [w for w in (gap(c, FROM, TO) for c in calls_in(runs[0])) if w]
        b = [w for w in (gap(c, FROM, TO) for c in calls_in(runs[1])) if w]
        if a and b:
            # The interval is for median(second) - median(first), so
            # print the difference the same way round as the interval.
            low, high = stats.bootstrap_difference_interval(a, b)
            second, first = runs[1].split("/")[-1], runs[0].split("/")[-1]
            print(f"\n{second} minus {first}: "
                  f"{statistics.median(b) - statistics.median(a):+.3f} s"
                  f"  (95% interval {low:+.3f} to {high:+.3f})")


def keys(run: str) -> None:
    """What the keypad sent, and how it arrived."""
    for n, call in enumerate(calls_in(run), 1):
        pressed = [r for r in call if r.get("stage") == "dtmf"]
        digits = "".join(r["digit"] for r in pressed)
        codes = ", ".join(str(r["code"]) for r in pressed)
        print(f"call {n}: {len(pressed)} event(s), digits {digits or '-'}")
        if pressed:
            print(f"  rfc 4733 codes: {codes}")
        heard = heard_in(call)
        print(f"  transcript:     {heard or '(nothing)'}")


def facts(run: str, only: int = 0) -> None:
    """What the signalling said, before anybody spoke."""
    for n, call in enumerate(calls_in(run), 1):
        if only and n != only:
            continue
        known = [r["facts"] for r in call if r.get("facts")]
        print(f"call {n}:")
        for key, value in (known[0] if known else {}).items():
            print(f"  {key:<24}{value}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--keys"]:
        keys(sys.argv[2])
    elif sys.argv[1:2] == ["--facts"]:
        rest = sys.argv[2:]
        pick = int(rest[rest.index("--call") + 1]) if "--call" in rest else 0
        facts(rest[0], pick)
    else:
        main(sys.argv[1:])
