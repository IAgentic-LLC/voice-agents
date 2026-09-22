"""Chapter 12: an agent that may or may not remember you.

Same cascaded stack, with a store of named facts and one tool for
writing to it. Start it and leave it running while caller.py places
calls:

    uv run memory_agent.py start

Settings (environment variables):
    AGENT_NAME    the name callers ask for (default "memory")
    MEMORY        "off" (default): nothing survives the call.
                  "on": named facts are kept per caller and read back
                  into the prompt at the start of the next one.
    STORE         where those facts are written
                  (default runs/mine/memory.jsonl)
    HOLD_OPEN     "on": keep the session alive when the caller
                  disconnects, by turning off
                  RoomOptions.close_on_disconnect (default "off",
                  which is LiveKit's own default: it closes on
                  CLIENT_INITIATED, ROOM_DELETED and USER_REJECTED,
                  and not on a timeout).
    VOICE         "off" here by default: what is measured is what the
                  agent said, which is in the trace either way.

The caller's identity, not the room, is the key. A room is one call; a
caller comes back.
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

from voicelab import config, cost, memory, runlog
from voicelab.trace import trace_session

AGENT_NAME = os.environ.get("AGENT_NAME", "memory")
MEMORY = os.environ.get("MEMORY", "off")
HOLD_OPEN = os.environ.get("HOLD_OPEN", "off")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")
STREAM_STT_MODEL = os.environ.get(
    "STREAM_STT_MODEL", "gemini-3.5-transcribe-live"
)
TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-3.1-flash-tts-preview")
VAD_SILENCE = float(os.environ.get("VAD_SILENCE", "1.2"))
VOICE = os.environ.get("VOICE", "off")

BASE = (
    "You are a support assistant who books callbacks. "
    "Answer in one short sentence, because you are on the telephone. "
    "If the caller tells you something you already know, say so."
)
KEEPS = BASE + (
    " You may keep a caller's name and the day and time of a callback "
    "for next time, by calling remember_fact. Never offer to keep "
    "anything else, and if they give you a card or account number, do "
    "not write it down."
)


def make_tool(store: str, caller: str, room: str, stages: str):
    @function_tool
    async def remember_fact(ctx: RunContext, fact: str, value: str) -> str:
        """Keep one fact about this caller for their next call.

        Args:
            fact: one of name, callback_day, callback_time
            value: what to keep, in the caller's own words
        """
        result = memory.remember(store, caller, fact, value)
        runlog.append(stages, {
            "stage": "trace", "room": room, "event": "remembered",
            "at": time.time(), "text": f"{fact}={value}",
            "kept": fact in memory.ALLOWED,
        })
        return result

    return remember_fact


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
    store = os.environ.get("STORE", f"{run_dir}/memory.jsonl")
    key = config.gemini_key()

    # The caller's identity is what persists. caller.py joins as
    # "caller", so every call in a run is the same person coming back.
    await ctx.connect()
    participant = await ctx.wait_for_participant()
    caller = participant.identity

    known = (memory.describe(store, caller) if MEMORY == "on"
             else "You have no record of this caller.")
    runlog.append(stages, {
        "stage": "config", "memory": MEMORY, "hold_open": HOLD_OPEN,
        "store": store, "caller": caller, "known": known,
        "llm": LLM_MODEL, "voice": VOICE, "vad_silence": VAD_SILENCE,
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

    tools = ([make_tool(store, caller, ctx.room.name, stages)]
             if MEMORY == "on" else [])
    await session.start(
        room=ctx.room,
        agent=Agent(instructions=(KEEPS if MEMORY == "on" else BASE)
                    + " " + known, tools=tools),
        room_options=room_io.RoomOptions(
            audio_output=VOICE == "on",
            close_on_disconnect=HOLD_OPEN != "on",
        ),
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
