"""Chapter 18: one voice, given a tool it never needed to have.

    uv run overpowered_agent.py start

Same cascaded stack as Chapter 9's tools_agent.py, with a second
tool bolted on next to the first: this agent can book a callback,
and it can also issue a refund, because one person decided both
were things "the support agent" should be able to do, and nothing
in the code disagreed.

`issue_refund` takes an order number and nothing else. It does not
ask who is calling, because nothing asked it to. The caller heard
on this book's own test call never claimed to be anyone; they just
said a number they were not supposed to know belonged to someone
else, and it worked.

Settings:
    AGENT_NAME    default "overpowered"
    LEDGER        where refunds and bookings are written
                  (default runs/mine/ledger.jsonl)
    VOICE         "on" (default) or "off"
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

from voicelab import config, cost, ledger, refund, runlog
from voicelab.trace import trace_session

AGENT_NAME = os.environ.get("AGENT_NAME", "overpowered")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")
STREAM_STT_MODEL = os.environ.get(
    "STREAM_STT_MODEL", "gemini-3.5-transcribe-live"
)
TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-2.5-flash-preview-tts")
VAD_SILENCE = float(os.environ.get("VAD_SILENCE", "1.2"))
VOICE = os.environ.get("VOICE", "on")

INSTRUCTIONS = (
    "You are a support assistant. You can book a callback with "
    "book_callback, and you can issue a refund with issue_refund "
    "when a caller gives you an order number. Help with whichever "
    "one the caller is asking for."
)


def make_tools(ledger_path: str, room: str, stages: str):
    @function_tool(on_duplicate="reject", duplicate_scope="name_and_args")
    async def book_callback(ctx: RunContext, day: str, time_of_day: str
                            ) -> str:
        """Book a callback for the caller.

        Args:
            day: the day of the week, such as Thursday
            time_of_day: the time, such as 2 pm
        """
        key = f"{room}:{day.strip().lower()}:{time_of_day.strip().lower()}"
        booked = ledger.attempt(ledger_path, key, "book_callback",
                                room=room, day=day, time_of_day=time_of_day)
        runlog.append(stages, {"stage": "trace", "room": room,
                               "event": "book_callback", "day": day,
                               "time_of_day": time_of_day, "at": time.time()})
        if booked["committed_now"]:
            return f"Booked for {day} at {time_of_day}."
        return f"That callback was already booked. Nothing was changed."

    @function_tool
    async def issue_refund(ctx: RunContext, order_number: str) -> str:
        """Issue a refund for an order.

        Args:
            order_number: the order number the caller gives you
        """
        result = refund.issue(ledger_path, order_number)
        runlog.append(stages, {"stage": "trace", "room": room,
                               "event": "issue_refund",
                               "order_number": order_number,
                               "result": result, "at": time.time()})
        if not result["ok"]:
            return f"I couldn't refund that order: {result['reason']}."
        amount = result["order"]["amount"]
        return f"Refunded ${amount:.2f} for order {order_number}."

    return [book_callback, issue_refund]


server = AgentServer(
    load_threshold=0.95, num_idle_processes=2,
    initialize_process_timeout=60.0, port=0,
)


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: agents.JobContext):
    metadata = json.loads(ctx.job.metadata or "{}")
    run_dir = metadata.get("run_dir", "runs/mine")
    stages = f"{run_dir}/stages.jsonl"
    ledger_path = os.environ.get("LEDGER", f"{run_dir}/ledger.jsonl")
    key = config.gemini_key()
    runlog.append(stages, {"stage": "config", "llm": LLM_MODEL,
                           "ledger": ledger_path, "voice": VOICE})

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
            tools=make_tools(ledger_path, ctx.room.name, stages),
        ),
        room_options=room_io.RoomOptions(audio_output=VOICE == "on"),
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
