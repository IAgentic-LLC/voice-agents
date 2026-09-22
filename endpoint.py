"""Chapter 6: did the agent wait for the whole question, and how long?

    uv run endpoint.py runs/ch06-a runs/ch06-b runs/ch06-c runs/ch06-d
    uv run endpoint.py --events runs/ch06-e 0.9
    uv run endpoint.py --stops runs/ch06-b

For each run and each pause length it counts the turns the question was
split into (one is right) and the time from the end of the caller's speech
to the agent handing the question to the model. With --events it prints
every event of the first call at one pause length instead, on one clock,
with zero at the end of the caller's speech. With --stops it prints, for
every call, the moments the voice detector said the caller had stopped.
Needs no key.
"""

import re
import statistics
import sys

from voicelab import runlog


def pause_of(call: dict) -> float:
    found = re.search(r"pause-(\d\.\d)", call.get("question", ""))
    return float(found.group(1)) if found else 0.9  # the original recording


def call_turns(call: dict, traces: list[dict]) -> tuple[int, float | None]:
    """How many final transcripts the question produced, and when (after
    T0, by the time it was written down) the model was first given the
    whole question."""
    t0 = call["speech_end_wall"]
    mine = [t for t in traces if t["room"] == call["room"]]
    finals = [t for t in mine if t["event"] == "final transcript"]
    thinking = sorted(t["t"] - t0 for t in mine
                      if t["event"] == "agent thinking" and t["t"] > t0)
    return len(finals), (thinking[0] if thinking else None)


def stops(run: str) -> None:
    """When the voice detector reported that the caller had stopped.

    One line per call. A time before zero is a report made during the
    pause in the middle of the question. `turns` is how many final
    transcripts the question produced: two means it was cut in half.
    """
    calls = [c for c in runlog.read(f"{run}/trials.jsonl")
             if "speech_end_wall" in c]
    traces = [s for s in runlog.read(f"{run}/stages.jsonl")
              if s["stage"] == "trace"]
    print(f"{'pause':>6}  detector stops at            turns")
    for call in sorted(calls, key=lambda c: (pause_of(c), c["t"])):
        t0 = call["speech_end_wall"]
        mine = [t for t in traces if t["room"] == call["room"]]
        at = [f"{t['t'] - t0:+.3f}" for t in mine
              if t["event"] == "user listening"]
        turns = len([t for t in mine if t["event"] == "final transcript"])
        print(f"{pause_of(call):>5.1f}s  {', '.join(at):<27}{turns:>4}")


def events(run: str, pause: float) -> None:
    """Every event of one call, in order, seconds from the end of speech.

    Each event is timed when the agent learned of it, which is what
    decides turns. The voice activity detector's own estimate of when
    speech stopped is earlier, by the silence it had to wait out.
    """
    calls = [c for c in runlog.read(f"{run}/trials.jsonl")
             if "speech_end_wall" in c and pause_of(c) == pause]
    traces = [s for s in runlog.read(f"{run}/stages.jsonl")
              if s["stage"] == "trace"]
    call = calls[0]
    t0 = call["speech_end_wall"]
    mine = sorted((t for t in traces if t["room"] == call["room"]),
                  key=lambda t: t["t"])
    for event in mine:
        text = event.get("text", "")
        said = f"  {text!r}" if text else ""
        print(f"{event['t'] - t0:+7.3f}  {event['event']:<17}{said}")


def main(runs: list[str]) -> None:
    print(f"{'run':<14}{'pause':>6}{'calls':>6}{'whole':>7}"
          f"{'hand-off, median':>18}")
    for run in runs:
        calls = [c for c in runlog.read(f"{run}/trials.jsonl")
                 if "speech_end_wall" in c]  # calls that got that far
        traces = [s for s in runlog.read(f"{run}/stages.jsonl")
                  if s["stage"] == "trace"]
        for pause in sorted({pause_of(c) for c in calls}):
            mine = [c for c in calls if pause_of(c) == pause]
            results = [call_turns(c, traces) for c in mine]
            whole = sum(n == 1 for n, _ in results)
            waits = [w for n, w in results if n == 1 and w is not None]
            wait = f"{statistics.median(waits):.3f} s" if waits else "-"
            name = run.split("/")[-1]
            print(f"{name:<14}{pause:>5.1f}s{len(mine):>6}"
                  f"{whole:>4} of {len(mine)}{wait:>13}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--events"]:
        events(sys.argv[2], float(sys.argv[3]))
    elif sys.argv[1:2] == ["--stops"]:
        stops(sys.argv[2])
    else:
        main(sys.argv[1:])
