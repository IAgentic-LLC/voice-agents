"""Chapter 14: the same agent, reached down a real SIP call.

    AGENT_NAME=p14 uv run phone_agent.py start

Chapter 13 argued that a keypress belongs in the signalling rather
than in the audio, and then could not prove it, because there was no
telephony leg to receive one. This agent has one. It sits on the far
end of a SIP trunk, and it writes down three things the earlier
agents never saw:

    sip attributes  what the trunk says about the caller: the number
                    they dialled from, the number they dialled, and
                    the call id, all from the signalling
    dtmf            each keypress as a named event, with its digit and
                    its RFC 4733 code, not a sound anybody had to
                    identify
    codec           what the media actually arrived as

Everything else is Chapter 5's cascaded stack, unchanged, so the
numbers can be compared with a browser call directly.

Settings are Chapter 5's, plus:
    VOICE         "on" (default) or "off"
    GREETING      what to say on answering (default: a short line, so
                  a caller hears something before they start talking)
"""

import json
import os
import time

from livekit import agents, rtc
from livekit.agents import Agent, AgentServer, AgentSession, inference, \
    room_io
from livekit.plugins import google, silero

from voicelab import config, cost, policy, runlog
from voicelab.trace import trace_session

LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")
STREAM_STT_MODEL = os.environ.get(
    "STREAM_STT_MODEL", "gemini-3.5-transcribe-live"
)
TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-2.5-flash-preview-tts")
AGENT_NAME = os.environ.get("AGENT_NAME", "p14")
VOICE = os.environ.get("VOICE", "on")
VAD_SILENCE = float(os.environ.get("VAD_SILENCE", "0.55"))
GREETING = os.environ.get(
    "GREETING", "Thanks for calling. How can I help?"
)

# The attributes a SIP participant carries. They come from the
# signalling, so they are facts rather than anything anybody heard.
SIP_KEYS = (
    "sip.callID",
    "sip.trunkID",
    "sip.phoneNumber",
    "sip.trunkPhoneNumber",
    "sip.callStatus",
    "sip.ruleID",
)


def sip_facts(participant: rtc.RemoteParticipant) -> dict:
    """Whatever the trunk told us about this caller."""
    attrs = participant.attributes or {}
    return {k: attrs[k] for k in SIP_KEYS if k in attrs}


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
    started = time.time()
    runlog.append(stages, {
        "stage": "config", "llm": LLM_MODEL, "tts": TTS_MODEL,
        "stt": STREAM_STT_MODEL, "voice": VOICE, "room": ctx.room.name,
        "leg": "sip",
    })

    # A keypress arrives here, named, with nothing to decode.
    @ctx.room.on("sip_dtmf_received")
    def on_dtmf(dtmf: rtc.SipDTMF):
        runlog.append(stages, {
            "stage": "dtmf", "room": ctx.room.name,
            "digit": dtmf.digit, "code": dtmf.code,
            "from": dtmf.participant.identity if dtmf.participant else None,
            "at": round(time.time(), 3),
            "since_start_s": round(time.time() - started, 3),
        })

    @ctx.room.on("participant_connected")
    def on_join(participant: rtc.RemoteParticipant):
        runlog.append(stages, {
            "stage": "sip", "room": ctx.room.name,
            "identity": participant.identity,
            "kind": str(participant.kind),
            "facts": sip_facts(participant),
            "at": round(time.time(), 3),
        })

    @ctx.room.on("track_subscribed")
    def on_track(track, publication, participant):
        # On an inbound call the caller is in the room before the
        # agent is, so participant_connected never fires for them.
        # This does, and by now the trunk's attributes are set.
        runlog.append(stages, {
            "stage": "track", "room": ctx.room.name,
            "kind": str(track.kind), "mime": publication.mime_type,
            "identity": participant.identity,
            "facts": sip_facts(participant),
            "at": round(time.time(), 3),
        })

    session = AgentSession(
        stt=google.beta.GeminiSTT(model=STREAM_STT_MODEL, api_key=key),
        llm=google.LLM(
            model=LLM_MODEL, api_key=key,
            thinking_config={"thinking_level": "low"},
        ),
        tts=google.beta.GeminiTTS(
            model=TTS_MODEL, voice_name="Puck", api_key=key
        ) if VOICE == "on" else None,
        vad=silero.VAD.load(min_silence_duration=VAD_SILENCE),
        turn_handling={
            "turn_detection": inference.TurnDetector(version="v1-mini"),
        },
    )

    async def log_usage():
        cost.record(session, stages)

    ctx.add_shutdown_callback(log_usage)
    trace_session(session, stages, ctx.room.name)

    # Anyone already in the room when the agent joined: on a SIP call
    # the caller is usually there first, so the handler above would
    # miss them.
    for participant in ctx.room.remote_participants.values():
        runlog.append(stages, {
            "stage": "sip", "room": ctx.room.name,
            "identity": participant.identity,
            "kind": str(participant.kind),
            "facts": sip_facts(participant),
            "at": round(time.time(), 3), "already_there": True,
        })

    await session.start(
        room=ctx.room,
        agent=Agent(instructions=policy.INSTRUCTIONS),
        room_options=room_io.RoomOptions(audio_output=VOICE == "on"),
    )
    if VOICE == "on" and GREETING:
        await session.say(GREETING)


if __name__ == "__main__":
    agents.cli.run_app(server)
