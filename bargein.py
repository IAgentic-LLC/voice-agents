"""Chapter 7: how long the agent kept talking after the caller cut in.

    uv run bargein.py runs/ch07-a runs/ch07-b runs/ch07-c
    uv run bargein.py --sweep runs/ch07-warmup-*
    uv run bargein.py --anatomy runs/ch07-a

For each run it reports the time from the caller's first loud frame to the
agent's last one (the stop), how much of the answer the caller heard after
they started talking, and whether the answer started again afterwards. A
run where the agent never stopped is reported as such. Needs no key.
"""

import statistics
import sys

from voicelab import runlog
from voicelab.stats import bootstrap_median_interval

# The recorded answer has its own pauses, the longest 0.62 s. A silence
# longer than this one is the agent having stopped, not a breath.
RESUMED_GAP_S = 1.0


def read(run: str) -> list[dict]:
    return [c for c in runlog.read(f"{run}/trials.jsonl")
            if c.get("stop_s") is not None]


def resumed(call: dict) -> bool:
    """Did the agent fall silent and then start speaking again?"""
    return any(gap >= RESUMED_GAP_S for _, gap in call.get("gaps", []))


def answer_s(run: str) -> float:
    for record in runlog.read(f"{run}/stages.jsonl"):
        if "answer_s" in record:
            return record["answer_s"]
    return 0.0


def main(runs: list[str]) -> None:
    print(f"{'run':<18}{'calls':>6}{'stopped after':>15}"
          f"{'heard after':>13}{'resumed':>9}")
    for run in runs:
        calls = read(run)
        if not calls:
            print(f"{run.split('/')[-1]:<18}{'no calls':>6}")
            continue
        whole = answer_s(run)
        # A "stop" as long as the answer means it was never interrupted:
        # the agent talked until the recording ran out.
        talked_on = sum(c["stop_s"] > whole - c["interrupt_after_s"] - 2
                        for c in calls)
        stops = [c["stop_s"] for c in calls]
        heard = [c["heard_after_s"] for c in calls]
        back = sum(resumed(c) for c in calls)
        name = run.split("/")[-1]
        stopped = ("never" if talked_on == len(calls)
                   else f"{statistics.median(stops):.3f} s")
        print(f"{name:<18}{len(calls):>6}{stopped:>15}"
              f"{statistics.median(heard):>11.2f} s"
              f"{back:>5} of {len(calls)}")


def sweep(runs: list[str]) -> None:
    """The same agent interrupted earlier and later in its own answer."""
    print(f"{'cut in at':>10}{'calls':>6}{'stopped after':>15}"
          f"{'95% interval':>22}")
    for run in sorted(runs, key=lambda r: float(r.rsplit("-", 1)[1])):
        calls = read(run)
        stops = [c["stop_s"] for c in calls]
        low, high = bootstrap_median_interval(stops)
        at = float(run.rsplit("-", 1)[1])
        print(f"{at:>9.1f}s{len(calls):>6}"
              f"{statistics.median(stops):>13.3f} s"
              f"{low:>16.3f} to {high:.3f}")


def anatomy(run: str) -> None:
    """Where the stop went, for one call, on the one clock of Chapter 4."""
    calls = read(run)
    traces = [s for s in runlog.read(f"{run}/stages.jsonl")
              if s.get("stage") == "trace"]
    call = calls[0]
    start = call["interrupt_start_wall"]
    mine = [t for t in traces if t["room"] == call["room"]]

    def first(event, after=True):
        times = [t["at"] for t in mine
                 if t["event"] == event and (t["at"] > start) == after]
        return min(times) - start if times else None

    steps = [
        ("caller's first loud frame goes out", 0.0),
        ("agent's detector hears speech", first("user speaking")),
        ("agent stops sending", first("agent listening")),
        ("caller's last agent audio", call["stop_s"]),
    ]
    for name, when in steps:
        print(f"{when:+7.3f}  {name}" if when is not None
              else f"      ?  {name}")
    print(f"\n{call['heard_after_s']:.2f} s of the answer played after the "
          f"caller started talking")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--anatomy"]:
        anatomy(sys.argv[2])
    elif sys.argv[1:2] == ["--sweep"]:
        sweep(sys.argv[2:])
    else:
        main(sys.argv[1:])
