"""Chapter 20: what proof survives a second handoff, and what the
technical agent does with what is left over.

    uv run capability_report.py runs/ch20-capability

Reads `handoff_agent.py`'s two events around the second handoff,
`handoff requested` and `technical on_enter`, the same way Chapter
19's report does. `technical on_enter` also carries the real item
types `TechnicalAgent`'s own chat context ended up with, straight
from the framework's own filtering, not from anything this book
computed. Whether a refund really happened is answered by the real
ledger file this run wrote, not by anything the technical agent
says about it. Long lines wrap at 74 columns, like every other
report in this book.
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
    issued = next((r for r in rows if r.get("event") == "issue_refund"), None)
    entered = next(
        (r for r in rows if r.get("event") == "technical on_enter"), None
    )
    said_after = [
        r for r in rows
        if r.get("event") == "assistant said"
        and entered and r["at"] >= entered["at"]
    ]

    if issued is None:
        print("no refund was issued in this run")
    else:
        result = issued["result"]
        print(f"issue_refund result: ok={result['ok']} "
              f"amount={result.get('amount')} "
              f"customer={result.get('customer')}")

    real = ledger.entries(f"{run}/ledger.jsonl")
    real_keys = [r["key"] for r in real]
    print(f"real ledger entries: {real_keys}")

    if entered is None:
        print("no second handoff happened in this run")
        return
    kinds = entered["carried_item_types"]
    print_wrapped("technical agent's carried item types: ", str(kinds))
    print(f"function_call in that list: {'function_call' in kinds}")
    print(f"function_call_output in that list: "
          f"{'function_call_output' in kinds}")

    if said_after:
        print_wrapped("technical agent said: ", f'"{said_after[0]["text"]}"')


if __name__ == "__main__":
    main(sys.argv[1])
