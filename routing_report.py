"""Chapter 21: how many times a caller got handed back and forth,
and whether anything ever stopped it.

    uv run routing_report.py runs/ch21-broken
    uv run routing_report.py runs/ch21-fixed

Counts every real `handoff requested` event in a run and reports the
highest bounce count reached, whether a `handoff blocked` event ever
fired, and what the agent said immediately after the last handoff
event of either kind. It does not judge whether that sentence
matches what actually happened; it just prints it next to the count,
so a reader can compare the two. Long lines wrap at 74 columns, like
every other report in this book.
"""

import sys
import textwrap

from voicelab import runlog


def print_wrapped(header: str, body: str) -> None:
    line = f"{header}{body}"
    if len(line) <= 78:
        print(line)
        return
    print(header.rstrip())
    for wrapped in textwrap.wrap(body.strip(), width=74):
        print("  " + wrapped)


def main(run: str) -> None:
    rows = runlog.read(f"{run}/stages.jsonl")
    handoffs = [r for r in rows if r.get("event") == "handoff requested"]
    blocked = [r for r in rows if r.get("event") == "handoff blocked"]
    print(f"handoffs: {len(handoffs)}")
    if handoffs:
        print(f"highest bounce count: {max(r['bounces'] for r in handoffs)}")
    print(f"blocked: {len(blocked)}")

    last_event = max(handoffs + blocked, key=lambda r: r["at"], default=None)
    if last_event is None:
        print("no routing events in this run")
        return
    said_after = [
        r for r in rows
        if r.get("event") == "assistant said" and r["at"] >= last_event["at"]
    ]
    if said_after:
        print_wrapped("agent said: ", f'"{said_after[0]["text"]}"')
    else:
        print("the agent never spoke after the last routing event")


if __name__ == "__main__":
    main(sys.argv[1])
