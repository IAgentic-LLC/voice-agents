"""Chapter 28: the same booking request, the same tool, three ways
for it to end, read straight from what each real call actually
logged.

    uv run failure_report.py runs/ch28-off runs/ch28-plain \\
        runs/ch28-tool-error

Long lines wrap at 74 columns, like every other report in this book.
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


def main(runs: list[str]) -> None:
    for run in runs:
        rows = runlog.read(f"{run}/stages.jsonl")
        fail_mode = next((r["fail_mode"] for r in rows
                          if r.get("stage") == "config"), "?")
        replies = [r for r in rows if r.get("event") == "assistant said"]
        print(f"{run} (fail_mode={fail_mode})")
        if replies:
            print_wrapped("  agent said: ", f'"{replies[0]["text"]}"')
        else:
            print("  agent said: nothing")
        print()


if __name__ == "__main__":
    main(sys.argv[1:])
