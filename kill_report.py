"""Chapter 29: what each real kill actually did to the call, read
straight from what kill_mid_call.py itself recorded.

    uv run kill_report.py runs/ch29-kill-wrapper runs/ch29-kill-tree
"""

import sys

from voicelab import runlog


def main(runs: list[str]) -> None:
    for run in runs:
        trial = runlog.read(f"{run}/trials.jsonl")[0]
        stages = runlog.read(f"{run}/stages.jsonl")
        said_after_kill = [
            s for s in stages
            if s.get("event") == "assistant said" and s["at"] > trial["kill_wall"]
        ]
        noticed = trial["disconnected_after_kill_s"]
        print(f"{trial['kill_mode']}: killed pids {trial['killed_pids']}")
        if said_after_kill:
            gap = said_after_kill[0]["at"] - trial["kill_wall"]
            print(f"  agent finished its reply {gap:.1f}s after the kill")
        else:
            print("  the agent never finished its reply")
        if noticed is None:
            print("  the caller's room never reported a disconnect")
        else:
            print(f"  disconnected_after_kill_s: {noticed}")


if __name__ == "__main__":
    main(sys.argv[1:])
