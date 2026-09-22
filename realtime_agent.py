"""Realtime voice agent: one speech-to-speech model hears and answers.

Start it and leave it running while caller.py places calls:

    uv run realtime_agent.py start

The caller passes the run directory in the dispatch metadata; token usage is
appended to <run dir>/stages.jsonl.
"""

import json
import os

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession
from livekit.plugins import google

from voicelab import config, cost, policy, runlog
from voicelab.trace import trace_session

MODEL = os.environ.get("REALTIME_MODEL", "gemini-3.8-live")
# Chapter 8 gives both agents the same policy to answer from, so their
# answers can be scored against the same facts. PROMPT=plain is what
# every earlier chapter used.
INSTRUCTIONS = (
    policy.INSTRUCTIONS if os.environ.get("PROMPT") == "policy"
    else "You are a concise customer support assistant. "
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
        cost.record(session, stages)  # Chapter 8

    ctx.add_shutdown_callback(log_usage)
    trace_session(session, stages, ctx.room.name)  # Chapter 4
    await session.start(room=ctx.room, agent=Agent(instructions=INSTRUCTIONS))


if __name__ == "__main__":
    agents.cli.run_app(server)
