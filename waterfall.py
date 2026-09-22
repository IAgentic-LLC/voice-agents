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
    ("user speaking", "agent reports caller speaking"),
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


# Each stage runs from one event to the next, measured within each call.
STAGES = [
    ("waiting out the silence", None, "user listening known"),
    ("transcription", "user listening known", "final transcript"),
    ("hand-off to the model", "final transcript", "agent thinking"),
    ("model's first token", "agent thinking", "first token"),
    ("first sentence voiced", "first token", "first speech byte"),
    ("start playing", "first speech byte", "agent speaking"),
    ("playing to heard", "agent speaking", "caller hears"),
]


def stage_lengths(events: dict[str, float]) -> dict[str, float]:
    out = {}
    for name, start, end in STAGES:
        begin = 0.0 if start is None else events.get(start)
        if begin is not None and end in events:
            out[name] = events[end] - begin
    return out


def main(run_dir: str) -> None:
    calls = [c for c in runlog.read(f"{run_dir}/trials.jsonl")
             if c.get("ok") and "first_audio_wall" in c]
    traces = [s for s in runlog.read(f"{run_dir}/stages.jsonl")
              if s["stage"] == "trace"]
    per_call = [call_events(c, traces) for c in calls]
    print(f"{len(per_call)} answered calls in {run_dir}")
    print(f"{'event, seconds after T0':<30}{'median':>9}{'fastest':>9}"
          f"{'slowest':>9}{'calls':>7}")
    rows = []
    for name, label in ORDER:
        times = [p[name] for p in per_call if name in p]
        if times:
            rows.append((statistics.median(times), label, times))
    for median, label, times in sorted(rows):  # in the order they happened
        print(f"{label:<30}{median:>8.3f}s"
              f"{min(times):>8.3f}s{max(times):>8.3f}s{len(times):>7}")
    if not any("first token" in p for p in per_call):
        return  # a realtime agent reports no stages inside its model
    stages = [stage_lengths(p) for p in per_call]
    # Median of each call's own stage length, and of each call's share of
    # its own wait. Medians of parts need not add up to the median whole.
    print()
    print(f"{'stage, within each call':<30}{'median':>9}{'share':>9}")
    for name, _, _ in STAGES:
        lengths = [s[name] for s, p in zip(stages, per_call) if name in s]
        shares = [s[name] / p["caller hears"]
                  for s, p in zip(stages, per_call) if name in s]
        if lengths:
            print(f"{name:<30}{statistics.median(lengths):>8.3f}s"
                  f"{100 * statistics.median(shares):>8.0f}%")


if __name__ == "__main__":
    main(sys.argv[1])
