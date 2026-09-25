"""Chapter 34: which organization's own instructions a real call
actually got, read straight from what that call's own worker wrote.

    uv run tenant_call_report.py runs/ch34-acme-call runs/ch34-globex-call
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
        print(f"{run} (org={config.get('org_id')}, "
              f"version {config.get('agent_version')})")
        if replies:
            print_wrapped("  agent said: ", f'"{replies[0]["text"]}"')
        else:
            print("  agent said: nothing")
        print()


if __name__ == "__main__":
    main(sys.argv[1:])
