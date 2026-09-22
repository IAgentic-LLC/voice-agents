"""Chapter 11: an agent that looks things up before it answers.

Same cascaded stack, with a tool that searches the passages in
voicelab/knowledge.py. Start it and leave it running while caller.py
places calls:

    uv run rag_agent.py start

Settings (environment variables):
    AGENT_NAME    the name callers ask for (default "rag")
    STYLE         "plain" (default): told to use the passages and
                  nothing else. "spoken": also told how to say it, and
                  told that the passage ids are not for the caller.
    HITS          how many passages the tool returns (default 2)
    VOICE         "off" here by default: this chapter measures the words
                  the agent chose, which are in the trace either way.
    VAD_SILENCE, LLM_MODEL, STREAM_STT_MODEL as in Chapter 9.

Every search is written to <run dir>/stages.jsonl with the passages it
returned, so what the agent was told can be read back later.
"""

import json
import os
import time

from livekit import agents
from livekit.agents import (
    Agent, AgentServer, AgentSession, RunContext, function_tool, inference,
    room_io,
)
from livekit.plugins import google, silero

from voicelab import config, cost, knowledge, runlog
from voicelab.trace import trace_session

AGENT_NAME = os.environ.get("AGENT_NAME", "rag")
STYLE = os.environ.get("STYLE", "plain")
HITS = int(os.environ.get("HITS", "2"))
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")
STREAM_STT_MODEL = os.environ.get(
    "STREAM_STT_MODEL", "gemini-3.5-transcribe-live"
)
TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-3.1-flash-tts-preview")
VAD_SILENCE = float(os.environ.get("VAD_SILENCE", "1.2"))
VOICE = os.environ.get("VOICE", "off")

PLAIN = (
    "You are a customer support assistant. "
    "Before answering any question about policy, call look_up and answer "
    "from the passages it returns. If they do not answer the question, "
    "say so. Do not use anything you were not given."
)
SPOKEN = PLAIN + (
    " You are speaking to someone on the telephone, so answer in one "
    "sentence. Give the single fact they asked for and stop. "
    "The passage ids are for our records and mean nothing to the "
    "caller, so never say an id out loud."
)


def make_tool(room: str, stages: str):
    @function_tool
    async def look_up(ctx: RunContext, question: str) -> str:
        """Search the support policy for a passage that answers a
        question.

        Args:
            question: what the caller wants to know, in their own words
        """
        hits = knowledge.search(question, limit=HITS)
        runlog.append(stages, {
            "stage": "trace", "room": room, "event": "looked up",
            "at": time.time(), "text": question,
            "passages": [h.passage_id for h in hits],
            "scores": [h.score for h in hits],
        })
        if not hits:
            return "Nothing in the policy covers that."
        return "\n".join(f"[{h.passage_id}] {h.text}" for h in hits)

    return look_up


server = AgentServer(
    load_threshold=0.95,
    num_idle_processes=2,
    initialize_process_timeout=60.0,
    port=0,
)


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: agents.JobContext):
    metadata = json.loads(ctx.job.metadata or "{}")
    run_dir = metadata.get("run_dir", "runs/mine")
    stages = f"{run_dir}/stages.jsonl"
    key = config.gemini_key()
    runlog.append(stages, {
        "stage": "config", "style": STYLE, "hits": HITS,
        "llm": LLM_MODEL, "stt": STREAM_STT_MODEL, "voice": VOICE,
        "tts": TTS_MODEL if VOICE == "on" else None,
        "vad_silence": VAD_SILENCE,
    })

    session = AgentSession(
        stt=google.beta.GeminiSTT(model=STREAM_STT_MODEL, api_key=key),
        llm=google.LLM(model=LLM_MODEL, api_key=key,
                       thinking_config={"thinking_level": "low"}),
        tts=google.beta.GeminiTTS(model=TTS_MODEL, voice_name="Puck",
                                  api_key=key) if VOICE == "on" else None,
        vad=silero.VAD.load(min_silence_duration=VAD_SILENCE),
        turn_handling={"turn_detection": inference.TurnDetector(
            version="v1-mini")},
    )

    async def log_usage():
        cost.record(session, stages)

    ctx.add_shutdown_callback(log_usage)
    trace_session(session, stages, ctx.room.name)

    await session.start(
        room=ctx.room,
        agent=Agent(instructions=SPOKEN if STYLE == "spoken" else PLAIN,
                    tools=[make_tool(ctx.room.name, stages)]),
        room_options=room_io.RoomOptions(audio_output=VOICE == "on"),
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
