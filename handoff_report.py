"""Chapter 19: what a handoff cost, and whether the caller had to
repeat themselves for it.

    uv run handoff_report.py runs/ch19-broken
    uv run handoff_report.py runs/ch19-fixed

Reads the same `stages.jsonl` every other report in this book reads,
looking for the two events `handoff_agent.py` writes around the
handoff itself: when the receptionist's tool asked for one, and when
the technical agent's `on_enter` fired. The gap between them is the
handoff's own latency. What the technical agent says first, read
straight from the trace rather than assumed, shows whether it asked
the caller to repeat the order number or already had it. Wrapped at
74 columns, like every other report in this book, so a long spoken
line stays inside the page.
"""

import sys
import textwrap

from voicelab import runlog


def main(run: str) -> None:
    rows = runlog.read(f"{run}/stages.jsonl")
    requested = next(
        (r for r in rows if r.get("event") == "handoff requested"), None
    )
    complete = next(
        (r for r in rows if r.get("event") == "handoff complete"), None
    )
    if requested is None:
        print("no handoff was requested in this run")
        return
    print(f"carry_context: {requested.get('carry_context')}")
    if complete is None:
        print("handoff requested but never completed")
        return
    print(f"handoff latency: {complete['at'] - requested['at']:.3f}s")
    said_after = [
        r for r in rows
        if r.get("event") == "assistant said" and r["at"] >= complete["at"]
    ]
    if said_after:
        line = f'technical agent said: "{said_after[0]["text"]}"'
        if len(line) > 78:
            print("technical agent said:")
            for wrapped in textwrap.wrap(f'"{said_after[0]["text"]}"',
                                         width=74):
                print("  " + wrapped)
        else:
            print(line)
    else:
        print("the technical agent never spoke")


if __name__ == "__main__":
    main(sys.argv[1])
