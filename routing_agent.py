"""Chapter 21: two agents that each think the caller belongs to the
other one, and a proactive greeting on both sides that can hand the
caller straight back without them saying another word.

    BOUNCE_GUARD=off AGENT_NAME=routing-broken uv run routing_agent.py start
    BOUNCE_GUARD=on  AGENT_NAME=routing-fixed  uv run routing_agent.py start

`SalesAgent` and `SupportAgent` both speak first on every handoff,
Chapter 19's own `on_enter` pattern for not leaving a caller in
silence. Each one's instructions ask it to hand the caller to the
other team when the question sounds like it belongs there. A
question that genuinely straddles both teams can satisfy both
conditions in the same breath, and a fresh `on_enter` reply, reading
the same carried complaint, has no memory of how many times this
has already happened, unless `voicelab/routing.py`'s own count is
threaded through by hand.

Settings:
    AGENT_NAME     default "routing"
    BOUNCE_GUARD   "on" (default) or "off"
    VOICE          "on" (default) or "off"
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

from voicelab import config, cost, handoff, routing, runlog
from voicelab.trace import trace_session

AGENT_NAME = os.environ.get("AGENT_NAME", "routing")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")
STREAM_STT_MODEL = os.environ.get(
    "STREAM_STT_MODEL", "gemini-3.5-transcribe-live"
)
TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-2.5-flash-preview-tts")
VAD_SILENCE = float(os.environ.get("VAD_SILENCE", "1.2"))
VOICE = os.environ.get("VOICE", "on")
BOUNCE_GUARD = os.environ.get("BOUNCE_GUARD", "on") != "off"

SALES_INSTRUCTIONS = (
    "You are sales. If the caller's message also describes a "
    "technical problem, such as a crash or a bug, call "
    "transfer_to_support right away, without asking anything first."
)

SUPPORT_INSTRUCTIONS = (
    "You are technical support. If the caller's message also "
    "describes a billing problem, such as a wrong charge, call "
    "transfer_to_sales right away, without asking anything first."
)

BLOCKED_MESSAGE = (
    "I'm having trouble routing this correctly. Let me get a person "
    "to help instead of passing you around again."
)


class SupportAgent(Agent):
    def __init__(self, *, chat_ctx, bounces: int, stages: str, room: str):
        @function_tool
        async def transfer_to_sales(context: RunContext) -> Agent | str:
            """Transfer the caller to sales. Call this once the
            caller's question turns out to be about billing or a
            plan change rather than a technical problem.
            """
            if BOUNCE_GUARD and routing.too_many_handoffs(bounces):
                runlog.append(stages, {
                    "stage": "routing", "room": room, "event":
                    "handoff blocked", "to": "sales", "bounces": bounces,
                    "at": time.time(),
                })
                return BLOCKED_MESSAGE
            runlog.append(stages, {
                "stage": "routing", "room": room,
                "event": "handoff requested", "to": "sales",
                "bounces": bounces, "at": time.time(),
            })
            current = context.session.current_agent
            carried = handoff.context_to_carry(current, True)
            return SalesAgent(
                chat_ctx=carried,
                bounces=routing.next_bounce_count(bounces),
                stages=stages, room=room,
            )

        super().__init__(instructions=SUPPORT_INSTRUCTIONS,
                         chat_ctx=chat_ctx, tools=[transfer_to_sales])
        self._stages = stages
        self._room = room
        self._bounces = bounces

    async def on_enter(self) -> None:
        runlog.append(self._stages, {
            "stage": "routing", "room": self._room,
            "event": "support on_enter", "bounces": self._bounces,
            "at": time.time(),
        })
        await self.session.generate_reply()


class SalesAgent(Agent):
    def __init__(self, *, chat_ctx, bounces: int, stages: str, room: str):
        @function_tool
        async def transfer_to_support(context: RunContext) -> Agent | str:
            """Transfer the caller to technical support. Call this
            once the caller's question turns out to be a technical
            problem rather than billing or a plan change.
            """
            if BOUNCE_GUARD and routing.too_many_handoffs(bounces):
                runlog.append(stages, {
                    "stage": "routing", "room": room, "event":
                    "handoff blocked", "to": "support", "bounces": bounces,
                    "at": time.time(),
                })
                return BLOCKED_MESSAGE
            runlog.append(stages, {
                "stage": "routing", "room": room,
                "event": "handoff requested", "to": "support",
                "bounces": bounces, "at": time.time(),
            })
            current = context.session.current_agent
            carried = handoff.context_to_carry(current, True)
            return SupportAgent(
                chat_ctx=carried,
                bounces=routing.next_bounce_count(bounces),
                stages=stages, room=room,
            )

        super().__init__(instructions=SALES_INSTRUCTIONS,
                         chat_ctx=chat_ctx, tools=[transfer_to_support])
        self._stages = stages
        self._room = room
        self._bounces = bounces

    async def on_enter(self) -> None:
        runlog.append(self._stages, {
            "stage": "routing", "room": self._room,
            "event": "sales on_enter", "bounces": self._bounces,
            "at": time.time(),
        })
        await self.session.generate_reply()


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
                           "voice": VOICE, "bounce_guard": BOUNCE_GUARD})

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
        agent=SalesAgent(chat_ctx=None, bounces=0, stages=stages,
                        room=ctx.room.name),
        room_options=room_io.RoomOptions(audio_output=VOICE == "on"),
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
