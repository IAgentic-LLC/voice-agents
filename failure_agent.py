"""Chapter 28: the same booking tool as Chapter 9, made to fail on
purpose, one way at a time, to see what the caller actually hears.

    FAIL_MODE=off AGENT_NAME=f28 uv run failure_agent.py start
    FAIL_MODE=plain AGENT_NAME=f28 uv run failure_agent.py start
    FAIL_MODE=tool_error AGENT_NAME=f28 uv run failure_agent.py start

Settings (environment variables):
    AGENT_NAME    the name callers ask for (default "failure")
    FAIL_MODE     "off" (default): book normally.
                  "plain": raise a plain ConnectionError, the SDK's
                  own fallback text is all the model ever sees.
                  "tool_error": raise a ToolError with a specific,
                  spoken-safe message instead.
    LEDGER        where bookings are written
                  (default runs/mine/ledger.jsonl)
    VOICE         "on" (default) or "off"

This is a copy of Chapter 9's tools_agent.py rather than an import
of it: the same cascaded stack, the same book_callback shape, one
tool argument added.
"""

import json
import os
import time

from livekit import agents
from livekit.agents import (
    Agent, AgentServer, AgentSession, RunContext, function_tool, inference,
    room_io,
)
from livekit.agents.llm import ToolError
from livekit.plugins import google, silero

from voicelab import config, cost, ledger, runlog
from voicelab.trace import trace_session

AGENT_NAME = os.environ.get("AGENT_NAME", "failure")
FAIL_MODE = os.environ.get("FAIL_MODE", "off")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")
STREAM_STT_MODEL = os.environ.get(
    "STREAM_STT_MODEL", "gemini-3.5-transcribe-live"
)
TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-2.5-flash-preview-tts")
VAD_SILENCE = float(os.environ.get("VAD_SILENCE", "1.2"))
VOICE = os.environ.get("VOICE", "on")

INSTRUCTIONS = (
    "You are a support assistant who books callbacks. "
    "When the caller asks for a callback, call book_callback with the "
    "day and time they asked for, then tell them what happened."
)

TOOL_ERROR_MESSAGE = (
    "I could not reach the booking system. Could I call you back "
    "once it is working again?"
)


def make_tool(ledger_path: str, room: str, stages: str):
    """The tool the model can call. FAIL_MODE decides whether it
    books, or fails, and if it fails, which way."""

    @function_tool
    async def book_callback(ctx: RunContext, day: str, time_of_day: str
                            ) -> str:
        """Book a callback for the caller.

        Args:
            day: the day of the week, such as Thursday
            time_of_day: the time, such as 2 pm
        """
        runlog.append(stages, {
            "stage": "trace", "room": room, "event": "tool called",
            "at": time.time(), "text": f"{day} {time_of_day}",
            "fail_mode": FAIL_MODE,
        })
        if FAIL_MODE == "plain":
            raise ConnectionError("booking service timed out")
        if FAIL_MODE == "tool_error":
            raise ToolError(TOOL_ERROR_MESSAGE)
        key = f"{room}:{day.strip().lower()}:{time_of_day.strip().lower()}"
        booked = ledger.attempt(
            ledger_path, key, "book_callback",
            room=room, day=day, time_of_day=time_of_day,
        )
        if booked["committed_now"]:
            return f"Booked for {day} at {time_of_day}."
        return (f"That callback was already booked for {day} at "
                f"{time_of_day}. Nothing was changed.")

    return book_callback


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
    ledger_path = os.environ.get("LEDGER", f"{run_dir}/ledger.jsonl")
    key = config.gemini_key()
    runlog.append(stages, {
        "stage": "config", "fail_mode": FAIL_MODE, "llm": LLM_MODEL,
        "ledger": ledger_path, "voice": VOICE,
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
        agent=Agent(
            instructions=INSTRUCTIONS,
            tools=[make_tool(ledger_path, ctx.room.name, stages)],
        ),
        room_options=room_io.RoomOptions(audio_output=VOICE == "on"),
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
