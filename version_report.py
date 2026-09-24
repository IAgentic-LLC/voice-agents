"""Chapter 31: what the same worker said, before and after a new
version added a tool it never had, read straight from what each
real call recorded. No code changed between these two runs.

    uv run version_report.py runs/ch31-v1 runs/ch31-v2
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
        config = next((r for r in rows if r.get("stage") == "config"), {})
        replies = [r for r in rows if r.get("event") == "assistant said"]
        print(f"{run} (version {config.get('agent_version')}, "
              f"tools={config.get('tools')})")
        if replies:
            print_wrapped("  agent said: ", f'"{replies[0]["text"]}"')
        else:
            print("  agent said: nothing")
        print()


if __name__ == "__main__":
    main(sys.argv[1:])
