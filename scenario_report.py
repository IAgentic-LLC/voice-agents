"""Chapter 23: what a scenario actually produced, checked against
the real ledger it wrote, not just the transcript it produced.

    uv run scenario_report.py runs/ch23-wrong-identity
    uv run scenario_report.py runs/ch23-injection

A caller's own words and an agent's reply are both just talk. The
ledger entry underneath them is the only line here that a tool
actually committed, so it is printed last, on its own, for a reader
to compare against everything said above it. Long lines wrap at 74
columns, like every other report in this book.
"""

import sys
import textwrap

from voicelab import ledger, runlog


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
    said = [r for r in rows if r.get("event") == "user said"]
    refunds = [r for r in rows if r.get("event") == "issue_refund"]
    replies = [r for r in rows if r.get("event") == "assistant said"]

    if said:
        print_wrapped("caller said: ", f'"{said[0]["text"]}"')
    for r in refunds:
        print(f"issue_refund called with order_number={r['order_number']}")
    if replies:
        print_wrapped("agent said: ", f'"{replies[0]["text"]}"')

    entries = ledger.entries(f"{run}/ledger.jsonl")
    if not entries:
        print("real ledger: no entry was written")
        return
    for e in entries:
        print(f"real ledger entry: order_id={e['order_id']} "
              f"amount={e['amount']} customer={e['customer']}")


if __name__ == "__main__":
    main(sys.argv[1])
