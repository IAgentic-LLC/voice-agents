"""Chapter 33: which lane answered each call, and which of those
calls crashed, read straight from what each call's own worker
already wrote, correlated by the room name every call is unique by.

    uv run canary_report.py runs/ch33-stable runs/ch33-canary runs/ch33-rolled-back
"""

import sys

from voicelab import runlog


def tally(run_dir: str) -> dict[str, dict[str, int]]:
    rows = runlog.read(f"{run_dir}/stages.jsonl")
    lane_of_room = {
        row["room"]: row["lane"] for row in rows if row.get("stage") == "config"
    }
    counts: dict[str, dict[str, int]] = {}
    for lane in lane_of_room.values():
        counts.setdefault(lane, {"calls": 0, "errors": 0})
        counts[lane]["calls"] += 1
    for row in rows:
        if row.get("stage") != "worker_error":
            continue
        lane = lane_of_room.get(row.get("room"), "unknown")
        counts.setdefault(lane, {"calls": 0, "errors": 0})
        counts[lane]["errors"] += 1
    return counts


def main(run_dirs: list[str]) -> None:
    for run_dir in run_dirs:
        counts = tally(run_dir)
        total = sum(c["calls"] for c in counts.values())
        print(f"{run_dir}: {counts} ({total} calls)")


if __name__ == "__main__":
    main(sys.argv[1:])
