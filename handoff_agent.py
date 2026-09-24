"""Chapter 19: a caller crosses from one agent to another without
hanging up.

    CARRY_CONTEXT=off uv run handoff_agent.py start   # the broken version
    CARRY_CONTEXT=on  uv run handoff_agent.py start    # the fixed version

A receptionist answers every call. When a caller describes a
technical problem, its own `transfer_to_technical` tool returns a
new `Agent` instance, and `AgentSession.update_agent()`, called by
the framework the moment a tool returns one, swaps which agent is
driving the call without the caller leaving the room or the call
ending. What the technical agent starts knowing depends on one
keyword argument this chapter's own `voicelab/handoff.py` names:
whether the receptionist's chat context is carried across, or
dropped.

Settings:
    AGENT_NAME      default "handoff"
    CARRY_CONTEXT   "on" (default) or "off": whether the technical
                    agent is built with the receptionist's own
                    conversation so far, or starts blank
    VOICE           "on" (default) or "off"
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

from voicelab import config, cost, handoff, runlog
from voicelab.trace import trace_session

AGENT_NAME = os.environ.get("AGENT_NAME", "handoff")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")
STREAM_STT_MODEL = os.environ.get(
    "STREAM_STT_MODEL", "gemini-3.5-transcribe-live"
)
TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-2.5-flash-preview-tts")
VAD_SILENCE = float(os.environ.get("VAD_SILENCE", "1.2"))
VOICE = os.environ.get("VOICE", "on")
CARRY_CONTEXT = os.environ.get("CARRY_CONTEXT", "on") != "off"

RECEPTIONIST_INSTRUCTIONS = (
    "You are a receptionist for a support line. Greet the caller and "
    "find out what they need. If they describe a technical problem "
    "with an order, call transfer_to_technical right away. Otherwise "
    "help them yourself."
)

TECHNICAL_INSTRUCTIONS = (
    "You are technical support. If the conversation so far already "
    "tells you the caller's order number, say so out loud and "
    "continue helping with that order directly. If you do not know "
    "the order number yet, ask for it before doing anything else."
)


class TechnicalAgent(Agent):
    def __init__(self, *, chat_ctx, stages: str, room: str):
        super().__init__(instructions=TECHNICAL_INSTRUCTIONS,
                         chat_ctx=chat_ctx)
        self._stages = stages
        self._room = room

    async def on_enter(self) -> None:
        runlog.append(self._stages, {
            "stage": "handoff", "room": self._room,
            "event": "handoff complete", "at": time.time(),
        })
        await self.session.generate_reply()


def make_receptionist(stages: str, room: str) -> Agent:
    @function_tool
    async def transfer_to_technical(context: RunContext) -> Agent:
        """Transfer the caller to technical support. Call this once
        the caller has described a technical problem with an order.
        """
        runlog.append(stages, {
            "stage": "handoff", "room": room,
            "event": "handoff requested", "carry_context": CARRY_CONTEXT,
            "at": time.time(),
        })
        current = context.session.current_agent
        carried = handoff.context_to_carry(current, CARRY_CONTEXT)
        return TechnicalAgent(chat_ctx=carried, stages=stages, room=room)

    return Agent(instructions=RECEPTIONIST_INSTRUCTIONS,
                tools=[transfer_to_technical])


server = AgentServer(
    load_threshold=0.95, num_idle_processes=2,
    initialize_process_timeout=60.0, port=0,
)


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: agents.JobContext):
    metadata = json.loads(ctx.job.metadata or "{}")
    run_dir = metadata.get("run_dir", "runs/mine")
    stages = f"{run_dir}/stages.jsonl"
    key = config.gemini_key()
    runlog.append(stages, {"stage": "config", "llm": LLM_MODEL,
                           "voice": VOICE, "carry_context": CARRY_CONTEXT})

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
        agent=make_receptionist(stages, ctx.room.name),
        room_options=room_io.RoomOptions(audio_output=VOICE == "on"),
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
