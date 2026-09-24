"""Chapter 29: the same two real Chapter 8 runs, priced by the
minute of call time and by the correct answer, not by the call.

    uv run cost_ledger_report.py runs/ch08-cascaded runs/ch08-realtime

Reuses compare.py's own pricing and voicelab/timeline.py's own event
reader; no new live call.
"""

import statistics
import sys

from compare import answers, priced, stages_of, usage_of
from report import summarize
from voicelab import runlog
from voicelab.profile import Profile
from voicelab.timeline import timeline


def call_minutes(run: str) -> list[float]:
    """Real wall-clock minutes for every room this run has a full
    event span for, Chapter 27's own first-to-last-event reading."""
    rooms = {t["room"] for t in runlog.read(f"{run}/trials.jsonl")
            if "room" in t}
    minutes = []
    for room in rooms:
        events = timeline(f"{run}/stages.jsonl", room)
        if len(events) >= 2:
            minutes.append((events[-1]["at"] - events[0]["at"]) / 60)
    return minutes


def build_ledger(run: str) -> Profile:
    scored = answers(run)
    right = sum(ok for _, _, ok in scored)
    waits = summarize(run)["ttfa"]
    costs, worked = [], set()
    for models in usage_of(run):
        money, missing = priced(models)
        costs.append(money)
        worked.update(m["model"] for m in models
                      if m["model"] not in missing)
    stages = stages_of(run)
    priced_stages = len([s for s in stages if s in worked])
    minutes = call_minutes(run)
    return Profile(
        run=run, right=right, total=len(scored),
        ttfa_median_s=statistics.median(waits),
        cost_per_call=statistics.median(costs),
        priced_stages=priced_stages, total_stages=len(stages),
        total_cost=sum(costs), total_minutes=sum(minutes),
    )


def main(runs: list[str]) -> None:
    print(f"{'run':<18}{'cost/call':>11}{'call minutes':>14}"
          f"{'cost/minute':>13}{'cost/success':>14}")
    for run in runs:
        p = build_ledger(run)
        name = run.split("/")[-1]
        per_min = (f"${p.cost_per_minute:.5f}"
                  if p.cost_per_minute is not None else "-")
        per_task = (f"${p.cost_per_successful_task:.5f}"
                   if p.cost_per_successful_task is not None else "-")
        print(f"{name:<18}${p.cost_per_call:<10.5f}{p.total_minutes:>13.3f}"
              f"{per_min:>13}{per_task:>14}")


if __name__ == "__main__":
    main(sys.argv[1:])
