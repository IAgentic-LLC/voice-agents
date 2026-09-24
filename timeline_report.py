"""Chapter 27: reconstruct one call end to end from its own
correlation id, and check whether the raw timeline's own biggest
gap actually points at the real bottleneck.

    uv run timeline_report.py runs/ch10-filler call-be4d237a
"""

import sys

from voicelab.timeline import biggest_gap, paired_duration, timeline


def main(run: str, room: str) -> None:
    events = timeline(f"{run}/stages.jsonl", room)
    if not events:
        print(f"no events found for room {room}")
        return

    t0 = events[0]["at"]
    for e in events:
        print(f"  {e['at'] - t0:+7.3f}s  {e['event']}")

    a, b, gap = biggest_gap(events)
    print(f"\nbiggest raw gap: {gap:.3f}s, between "
          f"\"{a['event']}\" and \"{b['event']}\"")

    tool_time = paired_duration(events, "tool called", "tool finished")
    if tool_time is not None:
        print(f"tool called to tool finished: {tool_time:.3f}s")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
