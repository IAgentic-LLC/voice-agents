"""Chapter 24: the same real calls, scored once as one number and
once per task, so a reader can see what the one number hides.

    uv run slice_report.py runs/ch11-plain runs/ch11-spoken runs/ch11-one
"""

import sys

from answers import scored


def main(runs: list[str]) -> None:
    by_task: dict[str, list[bool]] = {}
    total_right = total = 0
    for run in runs:
        for row in scored(run):
            total += 1
            total_right += row["right"]
            by_task.setdefault(row["task"], []).append(row["right"])

    print(f"aggregate: {total_right} of {total}")
    for task, results in by_task.items():
        print(f"{task:8s} {sum(results)} of {len(results)}")


if __name__ == "__main__":
    main(sys.argv[1:])
