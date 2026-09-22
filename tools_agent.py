"""Chapter 9: a voice agent that does something, and only once.

Same cascaded stack as Chapter 5, with one tool that books a callback and
writes it to a ledger. Start it and leave it running while caller.py
places calls:

    uv run tools_agent.py start

Settings (environment variables):
    AGENT_NAME    the name callers ask for (default "tools")
    CONFIRM       "off" (default): book as soon as the caller asks.
                  "on": read the booking back and wait for a yes.
    LEDGER        where bookings are written
                  (default runs/mine/ledger.jsonl)
    VAD_SILENCE   seconds of silence before a turn ends (default 1.2, the
                  value Chapter 1 settled on, not Silero's 0.55)
    VOICE         "on" (default) or "off"
    TOOL_DELAY    seconds the booking takes before it commits (default 0,
                  which returns at once as in Chapter 9)
    FILLER        "off" (default), or something for the agent to say while
                  the tool is still working (Chapter 10)
    CANCELLABLE   "on" marks the tool cancellable, so the framework may
                  stop it when the caller interrupts (default "off")

This is a copy of Chapter 5's cascaded stack rather than an import of
it: the same models, the streaming transcriber and the v1-mini turn
detector, with one tool attached. It does not take cascaded_agent.py's
other switches.
"""

import asyncio
import json
import os
import time

from livekit import agents
from livekit.agents import (
    Agent, AgentServer, AgentSession, RunContext, function_tool, inference,
    room_io,
)
from livekit.agents.llm import ToolFlag
from livekit.plugins import google, silero

from voicelab import config, cost, ledger, runlog
from voicelab.trace import trace_session

AGENT_NAME = os.environ.get("AGENT_NAME", "tools")
CONFIRM = os.environ.get("CONFIRM", "off")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")
STREAM_STT_MODEL = os.environ.get(
    "STREAM_STT_MODEL", "gemini-3.5-transcribe-live"
)
TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-2.5-flash-preview-tts")
VAD_SILENCE = float(os.environ.get("VAD_SILENCE", "1.2"))
VOICE = os.environ.get("VOICE", "on")
TOOL_DELAY = float(os.environ.get("TOOL_DELAY", "0"))
FILLER = os.environ.get("FILLER", "off")
CANCELLABLE = os.environ.get("CANCELLABLE", "off")

ACT_AT_ONCE = (
    "You are a support assistant who books callbacks. "
    "When the caller asks for a callback, call book_callback with the day "
    "and time they asked for, then tell them it is booked."
)
READ_IT_BACK = (
    "You are a support assistant who books callbacks. "
    "When the caller asks for a callback, do not book anything yet. "
    "Repeat the day and time back to them and ask if that is right. "
    "Only after they agree, call book_callback with that day and time. "
    "If they change the day or time, use the new one."
)


def make_tool(ledger_path: str, room: str, stages: str):
    """The tool the model can call. It closes over this call's ledger."""

    @function_tool(on_duplicate="reject", duplicate_scope="name_and_args",
                   flags=(ToolFlag.CANCELLABLE if CANCELLABLE == "on"
                          else ToolFlag.NONE))
    async def book_callback(ctx: RunContext, day: str, time_of_day: str
                            ) -> str:
        """Book a callback for the caller.

        Args:
            day: the day of the week, such as Thursday
            time_of_day: the time, such as 2 pm
        """
        # The key is the request, not the call: asking twice for the same
        # callback is one booking. A different day is a different one.
        key = f"{room}:{day.strip().lower()}:{time_of_day.strip().lower()}"
        runlog.append(stages, {
            "stage": "trace", "room": room, "event": "tool called",
            "at": time.time(), "text": f"{day} {time_of_day}",
        })
        if TOOL_DELAY:
            # Chapter 10: a booking system that thinks before it answers.
            # with_filler gives the agent something to say while it does,
            # once the session has been quiet for `delay` seconds.
            if FILLER != "off":
                async with ctx.with_filler(FILLER, delay=0.4):
                    await asyncio.sleep(TOOL_DELAY)
            else:
                await asyncio.sleep(TOOL_DELAY)
            runlog.append(stages, {
                "stage": "trace", "room": room, "event": "tool finished",
                "at": time.time(), "text": f"{TOOL_DELAY:.1f} s",
            })
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
        "stage": "config", "confirm": CONFIRM, "llm": LLM_MODEL,
        "ledger": ledger_path, "vad_silence": VAD_SILENCE, "voice": VOICE,
        "tool_delay": TOOL_DELAY, "filler": FILLER,
        "cancellable": CANCELLABLE,
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
            instructions=READ_IT_BACK if CONFIRM == "on" else ACT_AT_ONCE,
            tools=[make_tool(ledger_path, ctx.room.name, stages)],
        ),
        room_options=room_io.RoomOptions(audio_output=VOICE == "on"),
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
