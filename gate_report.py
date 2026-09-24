"""Chapter 25: scan every real recorded run this book has for a real
invariant violation, and refuse to call the release clean if it
finds one.

    uv run gate_report.py

This is a zero-violation gate: one real match, anywhere, in any run,
blocks the release. It does not average violations away, and it
does not stop at the first run that fails; every run is checked so
the count is real.
"""

import glob

from voicelab.invariants import (
    every_refund_matches_its_real_order,
    no_passage_id_spoken_aloud,
    no_run_exceeds_the_handoff_cap,
)


def main() -> None:
    run_dirs = sorted(
        d.rstrip("/\\").replace("\\", "/") for d in glob.glob("runs/*/")
    )
    total = 0
    for run in run_dirs:
        ids = no_passage_id_spoken_aloud(f"{run}/stages.jsonl")
        refunds = every_refund_matches_its_real_order(f"{run}/ledger.jsonl")
        bounces = no_run_exceeds_the_handoff_cap(f"{run}/stages.jsonl")
        if ids or refunds or bounces:
            total += len(ids) + len(refunds) + len(bounces)
            print(f"{run}: {len(ids)} id leak(s), {len(refunds)} refund "
                  f"mismatch(es), {len(bounces)} handoff(s) over cap")

    print()
    if total:
        print(f"release: BLOCKED  ({total} violation(s) across "
              f"{len(run_dirs)} runs)")
    else:
        print(f"release: clear  (0 violations across {len(run_dirs)} runs)")


if __name__ == "__main__":
    main()
