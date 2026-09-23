"""Show what the cascaded agent did in each call, in order.

    uv run timeline.py runs/ch01-cascaded-split
    uv run timeline.py runs/ch01-cascaded-split --call 2

For every call it lists the transcripts, each model call with its prompt
size, and each speech request with how much audio it produced and whether it
was cancelled. A cancelled request with 0.0 s of audio was never heard; one
with audio was heard until it was cut off.

Times are seconds from the moment the caller stopped speaking. Newer runs
record that moment. For the Chapter 1 runs it is estimated from when the
call record was written, so treat those times as approximate, to a few
tenths of a second. The order is reliable.
"""

import sys
import textwrap

from voicelab import runlog
from voicelab.question import speech_end_wall, wait_from_speech_end

LISTEN_S = 12.0  # caller.py keeps the line open this long after the question


def events_for(call: dict, stages: list[dict]) -> list[tuple]:
    if "question_s" not in call:  # the agent never joined: nothing to show
        return []
    # Times count from the moment the caller stopped speaking.
    end = speech_end_wall(call, LISTEN_S)
    rows = []
    for s in stages:
        if abs(s["t"] - end) > LISTEN_S + 2:
            continue
        if s["stage"] == "stt":
            rows.append((s["t"] - end, "heard", s["text"]))
        elif s["stage"] == "metrics":
            m = s["metrics"]
            at = m["timestamp"] - end
            if m["type"] == "llm_metrics":
                tokens = m["prompt_tokens"]
                rows.append((at, "model", f"{tokens} prompt tokens"))
            elif m["type"] == "tts_metrics":
                state = "cancelled" if m["cancelled"] else "finished"
                rows.append((at, "speech", f"{m['characters_count']} chars, "
                             f"{m['audio_duration']:.1f} s audio, {state}"))
    return sorted(rows)


def main(run_dir: str, only: int = 0) -> None:
    """Every call in the run, or just the one `only` names."""
    calls = runlog.read(f"{run_dir}/trials.jsonl")
    stages = runlog.read(f"{run_dir}/stages.jsonl")
    for call in calls:
        if only and call["call"] != only:
            continue
        wait = wait_from_speech_end(call) if call["ok"] else None
        result = f"answered, {wait:.3f} s" if call["ok"] else call["error"]
        print(f"call {call['call']}: {result}")
        for at, kind, detail in events_for(call, stages):
            lines = textwrap.wrap(detail, width=58) or [""]
            print(f"  {at:+6.2f} s  {kind:<7}{lines[0]}")
            for more in lines[1:]:
                print(f"{'':19}{more}")


if __name__ == "__main__":
    args = sys.argv[1:]
    call = int(args[args.index("--call") + 1]) if "--call" in args else 0
    main(args[0], call)
