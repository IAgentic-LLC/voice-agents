"""Chapter 29: what N calls landing on one worker at the same
moment did to each other's join time and time to first audio.

    uv run load_test_report.py runs/ch29-load-1 runs/ch29-load-5
"""

import statistics
import sys

from voicelab import runlog


def main(runs: list[str]) -> None:
    print(f"{'run':<18}{'calls':>6}{'answered':>10}{'join median':>13}"
          f"{'ttfa median':>13}")
    for run in runs:
        trials = runlog.read(f"{run}/trials.jsonl")
        answered = [t for t in trials if t.get("ok")]
        joins = [t["join_s"] for t in answered if "join_s" in t]
        ttfas = [t["ttfa_s"] for t in answered if "ttfa_s" in t]
        join = f"{statistics.median(joins):.3f}s" if joins else "-"
        ttfa = f"{statistics.median(ttfas):.3f}s" if ttfas else "-"
        print(f"{run.split('/')[-1]:<18}{len(trials):>6}"
              f"{len(answered):>6} of {len(trials)}{join:>13}{ttfa:>13}")


if __name__ == "__main__":
    main(sys.argv[1:])
