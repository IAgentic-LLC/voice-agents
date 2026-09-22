"""Chapter 4: one clock for every event in a call.

The caller and the agent are separate programs, but on one machine they
share the wall clock, time.time(). Every event is written with its wall
time and the room name, which is the call's id, so the two sides can be
lined up afterwards.
"""

import json

from livekit.agents import AgentSession

from voicelab import runlog


def record(path: str, room: str, event: str, t: float, **fields) -> None:
    runlog.append(path, {"stage": "trace", "room": room,
                         "event": event, "at": round(t, 4), **fields})


def trace_session(session: AgentSession, path: str, room: str) -> None:
    """Write the session's turn events to `path` as they happen."""

    @session.on("user_state_changed")
    def on_user(ev):
        record(path, room, f"user {ev.new_state}", ev.created_at)

    @session.on("agent_state_changed")
    def on_agent(ev):
        record(path, room, f"agent {ev.new_state}", ev.created_at)

    @session.on("user_input_transcribed")
    def on_transcript(ev):
        if ev.is_final:
            record(path, room, "final transcript", ev.created_at,
                   text=ev.transcript)

    @session.on("metrics_collected")
    def on_metrics(ev):
        m = json.loads(ev.metrics.model_dump_json())
        # Metrics arrive when a request finishes; work back to its start.
        if m["type"] == "llm_metrics" and m["ttft"] >= 0:
            start = m["timestamp"] - m["duration"]
            record(path, room, "first token", start + m["ttft"])
        if m["type"] == "tts_metrics" and m["ttfb"] >= 0:
            start = m["timestamp"] - m["duration"]
            record(path, room, "first speech byte", start + m["ttfb"])
