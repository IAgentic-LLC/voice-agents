"""Chapter 20: a refund's proof does not survive a second handoff to
an agent that was never given the tool that produced it.

    uv run capability_agent.py start

A receptionist hands billing questions to a billing agent, and the
billing agent hands technical questions on to a technical agent,
carrying its own chat context forward the way Chapter 19 does. The
billing agent has `issue_refund`; the technical agent does not, and
never receives it just because it inherits the conversation that
happened before it existed.

Settings:
    AGENT_NAME    default "capability"
    LEDGER        where refunds are written
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

from voicelab import config, cost, handoff, refund, runlog
from voicelab.trace import trace_session

AGENT_NAME = os.environ.get("AGENT_NAME", "capability")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")
STREAM_STT_MODEL = os.environ.get(
    "STREAM_STT_MODEL", "gemini-3.5-transcribe-live"
)
TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-2.5-flash-preview-tts")
VAD_SILENCE = float(os.environ.get("VAD_SILENCE", "1.2"))
VOICE = os.environ.get("VOICE", "on")

RECEPTIONIST_INSTRUCTIONS = (
    "You are a receptionist for a support line. If the caller wants "
    "a refund, call transfer_to_billing right away."
)

BILLING_INSTRUCTIONS = (
    "You are billing. If the caller gives an order number, call "
    "issue_refund. If the caller then describes a technical "
    "problem, call transfer_to_technical."
)

TECHNICAL_INSTRUCTIONS = (
    "You are technical support. If your own conversation so far "
    "already proves a refund went through, say so using that proof. "
    "If it does not, do not claim one happened; say you cannot "
    "confirm it from here."
)


class TechnicalAgent(Agent):
    def __init__(self, *, chat_ctx, stages: str, room: str):
        super().__init__(instructions=TECHNICAL_INSTRUCTIONS,
                         chat_ctx=chat_ctx)
        self._stages = stages
        self._room = room

    async def on_enter(self) -> None:
        kinds = [item.type for item in self.chat_ctx.items]
        runlog.append(self._stages, {
            "stage": "handoff", "room": self._room,
            "event": "technical on_enter", "carried_item_types": kinds,
            "has_refund_proof": "function_call_output" in kinds,
            "at": time.time(),
        })
        await self.session.generate_reply()


class BillingAgent(Agent):
    def __init__(self, *, chat_ctx, ledger_path: str, stages: str,
                room: str):
        @function_tool
        async def issue_refund(context: RunContext, order_number: str
                               ) -> str:
            """Issue a refund for an order.

            Args:
                order_number: the order number the caller gives you
            """
            result = refund.issue(ledger_path, order_number)
            runlog.append(stages, {"stage": "handoff", "room": room,
                                   "event": "issue_refund",
                                   "order_number": order_number,
                                   "result": result, "at": time.time()})
            if not result["ok"]:
                return f"I couldn't refund that order: {result['reason']}."
            amount = result["order"]["amount"]
            return f"Refunded ${amount:.2f} for order {order_number}."

        @function_tool
        async def transfer_to_technical(context: RunContext) -> Agent:
            """Transfer the caller to technical support. Call this
            once the caller describes a technical problem with an
            order.
            """
            runlog.append(stages, {"stage": "handoff", "room": room,
                                   "event": "handoff requested",
                                   "to": "technical", "at": time.time()})
            current = context.session.current_agent
            carried = handoff.context_to_carry(current, True)
            return TechnicalAgent(chat_ctx=carried, stages=stages,
                                  room=room)

        super().__init__(instructions=BILLING_INSTRUCTIONS,
                         chat_ctx=chat_ctx,
                         tools=[issue_refund, transfer_to_technical])
        self._stages = stages
        self._room = room

    async def on_enter(self) -> None:
        runlog.append(self._stages, {
            "stage": "handoff", "room": self._room,
            "event": "billing on_enter", "at": time.time(),
        })
        await self.session.generate_reply()


def make_receptionist(ledger_path: str, stages: str, room: str) -> Agent:
    @function_tool
    async def transfer_to_billing(context: RunContext) -> Agent:
        """Transfer the caller to billing. Call this once the caller
        asks for a refund.
        """
        runlog.append(stages, {"stage": "handoff", "room": room,
                               "event": "handoff requested",
                               "to": "billing", "at": time.time()})
        current = context.session.current_agent
        carried = handoff.context_to_carry(current, True)
        return BillingAgent(chat_ctx=carried, ledger_path=ledger_path,
                            stages=stages, room=room)

    return Agent(instructions=RECEPTIONIST_INSTRUCTIONS,
                tools=[transfer_to_billing])


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
                           "voice": VOICE, "ledger": ledger_path})

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
        agent=make_receptionist(ledger_path, stages, ctx.room.name),
        room_options=room_io.RoomOptions(audio_output=VOICE == "on"),
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
