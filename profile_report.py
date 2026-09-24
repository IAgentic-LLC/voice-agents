"""Chapter 22: the same two runs, as a profile, and then collapsed
into one score twice with two different honest-looking weightings.

    uv run profile_report.py runs/ch08-cascaded runs/ch08-realtime

The profile table is the same three numbers `compare.py` already
prints for Chapter 8, plus how much of the cost figure is actually
priced rather than silently missing. The two collapsed scores below
it use the same two profiles and nothing else; only the weights
change between them.
"""

import statistics
import sys

from compare import answers, priced, stages_of, usage_of
from report import summarize
from voicelab.profile import Profile, one_score


def build_profile(run: str) -> Profile:
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
    return Profile(
        run=run, right=right, total=len(scored),
        ttfa_median_s=statistics.median(waits),
        cost_per_call=statistics.median(costs),
        priced_stages=priced_stages, total_stages=len(stages),
    )


def main(runs: list[str]) -> None:
    profiles = [build_profile(r) for r in runs]

    print(f"{'run':<18}{'task success':>13}{'ttfa median':>13}"
          f"{'cost/call':>12}{'cost known':>12}")
    for p in profiles:
        name = p.run.split("/")[-1]
        known = f"{p.priced_stages} of {p.total_stages}"
        print(f"{name:<18}{p.task_success:>12.0%}"
              f"{p.ttfa_median_s:>12.3f}s{p.cost_per_call:>12.5f}"
              f"{known:>12}")

    max_wait = max(p.ttfa_median_s for p in profiles)
    max_cost = max(p.cost_per_call for p in profiles)

    for label, weight_speed, weight_cost in [
        ("speed-weighted (0.5 speed, 0.2 cost)", 0.5, 0.2),
        ("cost-weighted (0.1 speed, 0.7 cost)", 0.1, 0.7),
    ]:
        print(f"\n{label}:")
        for p in profiles:
            score = one_score(p, weight_speed=weight_speed,
                              weight_cost=weight_cost,
                              max_wait_s=max_wait, max_cost=max_cost)
            print(f"  {p.run.split('/')[-1]:<16}{score:.3f}")


if __name__ == "__main__":
    main(sys.argv[1:])
