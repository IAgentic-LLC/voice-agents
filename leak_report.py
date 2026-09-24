"""Chapter 18: how far apart the agent's two powers actually fired.

    uv run leak_report.py runs/ch18-leak

Prints the turn-level events relative to the moment the caller
started speaking: what was heard, what fired, what was said back.
It leaves out two kinds of row on purpose, not by trimming this
run's own output after the fact: `user said` repeats `final
transcript`'s own text verbatim, and `first token`/`first speech
byte` are per-frame streaming latency markers that belong to
Chapter 4's own waterfall, not to this chapter's question of which
tool fired when. `--full` prints every row `runlog` recorded,
unfiltered, for a reader who wants to check that nothing else is
being hidden.
"""

import sys
import textwrap

from voicelab import runlog

SKIP = {"user said", "first token", "first speech byte"}


def main(run: str, full: bool = False) -> None:
    rows = [r for r in runlog.read(f"{run}/stages.jsonl") if "at" in r]
    if not full:
        rows = [r for r in rows if r["event"] not in SKIP]
    if not rows:
        return
    t0 = next(r["at"] for r in rows if r["event"] == "user speaking")
    for r in rows:
        extra = ""
        if r["event"] in ("final transcript", "user said", "assistant said"):
            extra = f'  "{r.get("text", "")}"'
        elif r["event"] == "book_callback":
            extra = f"  {r['day']} {r['time_of_day']}"
        elif r["event"] == "issue_refund":
            res = r["result"]
            extra = (f"  order={r['order_number']} ok={res['ok']} "
                    f"amount={res.get('amount')} "
                    f"customer={res.get('customer')}")
        head = f"  {r['at'] - t0:+7.3f}s  {r['event']:<16}"
        if len(head) + len(extra) > 78:
            print(head.rstrip())
            for wrapped in textwrap.wrap(extra.strip(), width=74):
                print("    " + wrapped)
        else:
            print((head + extra).rstrip())


if __name__ == "__main__":
    main(sys.argv[1], full="--full" in sys.argv[2:])
