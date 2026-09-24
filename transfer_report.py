"""Chapter 17: what actually happened during a transfer, in order.

    uv run transfer_report.py runs/ch17-warm-transfer
    uv run transfer_report.py runs/ch17-duplicate-bug --transfers-only

Prints every traced event with its time relative to the first one,
the same shape Chapter 15's `outbound.py report` uses: a state
machine read from the log, not a story told from memory.
`--transfers-only` drops every row except the transfer tool's own
requested/result events, for a run whose point is how many times it
fired, not the conversation around it.
"""

import sys
import textwrap

from voicelab import runlog


def main(run: str, transfers_only: bool = False) -> None:
    rows = [r for r in runlog.read(f"{run}/stages.jsonl")
           if r.get("stage") != "config"]
    if transfers_only:
        rows = [r for r in rows if r.get("stage") == "transfer"]
    if not rows:
        return
    t0 = rows[0]["t"]
    for r in rows:
        event = r.get("event", r["stage"])
        extra = ""
        if event in ("assistant said", "user said", "final transcript"):
            extra = f'  "{r.get("text", "")}"'
        elif r["stage"] == "sip":
            facts = r.get("facts", {})
            extra = (f"  identity={r.get('identity')} "
                    f"to={facts.get('sip.phoneNumber', '')}")
        elif r["stage"] == "transfer" and event == "result":
            # identity and call_id are already on the sip line above;
            # repeating them here would only add width, not information.
            result = r.get("result", {})
            extra = "  ok=" + str(result.get("ok"))
            if not result.get("ok"):
                extra += f" {result.get('error', result.get('reason'))}"
        head = f"  {r['t'] - t0:+7.3f}s  {event:<20}"
        # A real value that pushes the line past this book's 78-column
        # limit is wrapped onto its own indented line rather than
        # trimmed: everything printed here is still the real value,
        # just not on one line.
        if len(head) + len(extra) > 78:
            print(head.rstrip())
            for wrapped in textwrap.wrap(extra.strip(), width=74):
                print("    " + wrapped)
        else:
            print((head + extra).rstrip())


if __name__ == "__main__":
    main(sys.argv[1], transfers_only="--transfers-only" in sys.argv[2:])
