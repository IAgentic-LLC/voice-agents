"""Chapter 4: where the wait goes, stage by stage, on one clock.

    uv run waterfall.py runs/ch04-cascaded

For each call it lines up the caller's and the agent's events from the
moment the caller stopped speaking, then prints the median time of each
event across calls. Needs no key: it reads the run's records.
"""

import statistics
import sys

from voicelab import runlog

# The events a turn passes through, in the order they should happen.
ORDER = [
    ("user listening", "speech stopped (agent's guess)"),
    ("user listening known", "agent knows speech stopped"),
    ("final transcript", "final transcript ready"),
    ("agent thinking", "turn handed to the model"),
    ("first token", "model's first token"),
    ("first speech byte", "voice's first audio byte"),
    ("agent speaking", "agent starts playing audio"),
    ("caller gets sound", "first faint sound arrives"),
    ("caller hears", "caller hears the answer"),
]


def call_events(call: dict, traces: list[dict]) -> dict[str, float]:
    """Seconds from the end of speech to the first time each event
    happened after it, for one call."""
    t0 = call["speech_end_wall"]
    mine = [t for t in traces if t["room"] == call["room"]]
    found = {}
    for name, _ in ORDER:
        # "known" is when the event was written down; the event's own time
        # can be an estimate made afterwards.
        event, field = name.removesuffix(" known"), "at"
        if name.endswith(" known"):
            field = "t"
        # Every event of this turn comes after the speech stops, give or
        # take the detector's own estimate.
        after = [t[field] - t0 for t in mine
                 if t["event"] == event and t[field] > t0 - 0.5]
        if after:
            found[name] = min(after)
    if "first_any_wall" in call:
        found["caller gets sound"] = call["first_any_wall"] - t0
    found["caller hears"] = call["first_audio_wall"] - t0
    return found


def main(run_dir: str) -> None:
    calls = [c for c in runlog.read(f"{run_dir}/trials.jsonl")
             if c.get("ok") and "first_audio_wall" in c]
    traces = [s for s in runlog.read(f"{run_dir}/stages.jsonl")
              if s["stage"] == "trace"]
    per_call = [call_events(c, traces) for c in calls]
    print(f"{len(per_call)} answered calls in {run_dir}")
    print(f"{'event':<30}{'median':>9}{'fastest':>9}{'slowest':>9}"
          f"{'calls':>7}")
    for name, label in ORDER:
        times = [p[name] for p in per_call if name in p]
        if not times:
            continue
        print(f"{label:<30}{statistics.median(times):>8.3f}s"
              f"{min(times):>8.3f}s{max(times):>8.3f}s{len(times):>7}")


if __name__ == "__main__":
    main(sys.argv[1])
