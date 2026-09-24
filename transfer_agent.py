"""Chapter 17: a phone agent that can put a caller through to a human.

    AGENT_NAME=p17 uv run transfer_agent.py start

Same SIP-aware base as Chapter 14's phone_agent.py, plus one tool,
`transfer_to_human`, that the model can call when a caller asks for
one. The tool never tells the caller they were transferred because
it asked to be; it tells them what `voicelab/transfer.py`'s own
status field actually says.

Settings, in addition to Chapter 14's:
    TRANSFER_MODE   "cold" (default) or "warm"
    TRANSFER_TO     tel:+E164 number the transfer goes to
    SIP_OUTBOUND_TRUNK_ID  needed only for TRANSFER_MODE=warm, which
                    dials the human itself rather than asking the
                    carrier to move the existing call
"""

import json
import os
import time

from livekit import agents, rtc
from livekit.agents import (
    Agent, AgentServer, AgentSession, RunContext, function_tool, inference,
    room_io,
)
from livekit.plugins import google, silero

from voicelab import config, cost, policy, runlog, transfer
from voicelab.trace import trace_session

LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")
STREAM_STT_MODEL = os.environ.get(
    "STREAM_STT_MODEL", "gemini-3.5-transcribe-live"
)
TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-2.5-flash-preview-tts")
AGENT_NAME = os.environ.get("AGENT_NAME", "p17")
VOICE = os.environ.get("VOICE", "on")
VAD_SILENCE = float(os.environ.get("VAD_SILENCE", "0.55"))
GREETING = os.environ.get(
    "GREETING", "Thanks for calling. How can I help?"
)
TRANSFER_MODE = os.environ.get("TRANSFER_MODE", "cold")
TRANSFER_TO = os.environ.get("TRANSFER_TO", "")
TRUNK_ID = os.environ.get("SIP_OUTBOUND_TRUNK_ID", "")

SIP_KEYS = (
    "sip.callID", "sip.callIDFull", "sip.trunkID", "sip.phoneNumber",
    "sip.trunkPhoneNumber", "sip.callStatus", "sip.ruleID",
)


def sip_facts(participant: rtc.RemoteParticipant) -> dict:
    attrs = participant.attributes or {}
    return {k: attrs[k] for k in SIP_KEYS if k in attrs}


def make_tool(room, caller_identity: dict, stages: str):
    """The transfer tool. It closes over the room the caller is in
    and a mutable box holding the caller's own participant identity,
    read fresh at call time rather than captured up front: on an
    outbound call the caller has not joined yet when this closure is
    built, so a value read then, instead of a live reference read
    now, would be `None` for the whole life of the call."""

    @function_tool(on_duplicate="reject", duplicate_scope="name_and_args")
    async def transfer_to_human(ctx: RunContext) -> str:
        """Transfer the caller to a human. Call this only when the
        caller has clearly asked to speak to a person.

        `on_duplicate="reject"` stops the model calling this a
        second time while the first call is still in flight; a real
        test call asked three times in the same breath and got three
        real dials to a human before this was added. It does not
        stop a call placed *after* an earlier one already succeeded,
        which is why a successful transfer disconnects the agent
        directly below rather than trusting the model to leave once
        told to.
        """
        runlog.append(stages, {"stage": "transfer", "room": room.name,
                               "event": "requested", "mode": TRANSFER_MODE,
                               "at": time.time()})
        if TRANSFER_MODE == "warm":
            result = await transfer.warm_transfer(
                room, TRANSFER_TO, TRUNK_ID)
        else:
            result = await transfer.cold_transfer(
                room.name, caller_identity["value"], TRANSFER_TO)
        runlog.append(stages, {"stage": "transfer", "room": room.name,
                               "event": "result", "mode": TRANSFER_MODE,
                               "result": result, "at": time.time()})
        if result.get("ok"):
            await ctx.session.say(
                "You're through. Goodbye.", allow_interruptions=False)
            runlog.append(stages, {"stage": "transfer", "room": room.name,
                                   "event": "agent leaving",
                                   "at": time.time()})
            await room.disconnect()
            return "Transferred and disconnected."
        return (f"The transfer did not go through ({result}). Tell the "
                f"caller honestly that you could not reach anyone and "
                f"ask if they would like to try again or leave a "
                f"message.")

    return transfer_to_human


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
    runlog.append(stages, {
        "stage": "config", "llm": LLM_MODEL, "voice": VOICE,
        "transfer_mode": TRANSFER_MODE, "room": ctx.room.name,
    })

    caller_identity = {"value": None}

    @ctx.room.on("participant_connected")
    def on_join(participant: rtc.RemoteParticipant):
        if caller_identity["value"] is None:
            caller_identity["value"] = participant.identity
        runlog.append(stages, {
            "stage": "sip", "room": ctx.room.name,
            "identity": participant.identity,
            "facts": sip_facts(participant), "at": round(time.time(), 3),
        })

    for participant in ctx.room.remote_participants.values():
        if caller_identity["value"] is None:
            caller_identity["value"] = participant.identity

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
            instructions=policy.INSTRUCTIONS + " If the caller asks to "
            "speak to a person, call transfer_to_human.",
            tools=[make_tool(ctx.room, caller_identity, stages)],
        ),
        room_options=room_io.RoomOptions(audio_output=VOICE == "on"),
    )
    if VOICE == "on" and GREETING:
        await session.say(GREETING)


if __name__ == "__main__":
    agents.cli.run_app(server)
