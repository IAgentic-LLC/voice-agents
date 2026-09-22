"""Realtime voice agent: one speech-to-speech model hears and answers.

Start it and leave it running while caller.py places calls:

    uv run realtime_agent.py start

The caller passes the run directory in the dispatch metadata; token usage is
appended to <run dir>/stages.jsonl.
"""

import dataclasses
import json
import os

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession
from livekit.plugins import google

from voicelab import config, runlog

MODEL = os.environ.get("REALTIME_MODEL", "gemini-3.8-live")
INSTRUCTIONS = (
    "You are a concise customer support assistant. "
    "Answer in one or two short sentences."
)

# Local-machine settings. The default CPU threshold (0.7) made a busy laptop
# refuse calls, and a fresh install on Windows can take longer than the
# default 10 s to start a worker process.
server = AgentServer(
    load_threshold=0.95,
    num_idle_processes=2,
    initialize_process_timeout=60.0,
)


@server.rtc_session(agent_name="realtime")
async def entrypoint(ctx: agents.JobContext):
    metadata = json.loads(ctx.job.metadata or "{}")
    run_dir = metadata.get("run_dir", "runs/mine")
    stages = f"{run_dir}/stages.jsonl"
    runlog.append(stages, {"stage": "config", "model": MODEL})

    model = google.realtime.RealtimeModel(
        model=MODEL, api_key=config.gemini_key(), voice="Puck"
    )
    session = AgentSession(llm=model)

    async def log_usage():
        try:  # a logging failure must never break a call
            usage = dataclasses.asdict(session.usage)
            runlog.append(stages, {"stage": "usage", "usage": usage})
        except Exception as exc:
            error = {"stage": "usage_error", "error": repr(exc)}
            runlog.append(stages, error)

    ctx.add_shutdown_callback(log_usage)
    await session.start(room=ctx.room, agent=Agent(instructions=INSTRUCTIONS))


if __name__ == "__main__":
    agents.cli.run_app(server)
