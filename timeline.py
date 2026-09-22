"""Show what the cascaded agent did in each call, in order.

    uv run timeline.py runs/ch01-cascaded-split

For every call it lists the transcripts, each model call with its prompt
size, and each speech request with how much audio it produced and whether it
was cancelled. A cancelled request with 0.0 s of audio was never heard; one
with audio was heard until it was cut off.

Times are seconds from the end of the caller's question, estimated from
when the call record was written (12 s after the question ended). Treat
them as approximate, to a few tenths of a second. The order is reliable.
"""

import sys
import textwrap

from voicelab import runlog

LISTEN_S = 12.0  # caller.py keeps the line open this long after the question


def events_for(call: dict, stages: list[dict]) -> list[tuple]:
    # Newer runs record the end of the question; older ones are estimated.
    end = call.get("speech_end_wall", call["t"] - LISTEN_S)
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


def main(run_dir: str) -> None:
    calls = runlog.read(f"{run_dir}/trials.jsonl")
    stages = runlog.read(f"{run_dir}/stages.jsonl")
    for call in calls:
        wait = call.get("ttfa_s")
        result = f"answered, {wait:.3f} s" if call["ok"] else call["error"]
        print(f"call {call['call']}: {result}")
        for at, kind, detail in events_for(call, stages):
            lines = textwrap.wrap(detail, width=58) or [""]
            print(f"  {at:+6.2f} s  {kind:<7}{lines[0]}")
            for more in lines[1:]:
                print(f"{'':19}{more}")


if __name__ == "__main__":
    main(sys.argv[1])
