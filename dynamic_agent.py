"""Chapter 31: an agent built at call time from a persisted,
versioned definition, instead of from a hardcoded instructions
string and a hardcoded tool list.

    uv run dynamic_agent.py start

Every agent since Chapter 9 has been one `.py` file per behavior.
This file is every behavior: which instructions, which model, which
tools, come from the `AgentVersion` this run loads, not from this
file's own source.

Settings (environment variables):
    AGENT_NAME    the name callers ask for, and the registry key
                  this worker loads its version under (default
                  "dynabook")
    AGENT_ORG     the organization this worker's rows belong to,
                  when a call's own dispatch metadata carries no
                  "org_id" of its own (default "default")
    AGENT_DB      the registry's own SQLite file
                  (default runs/registry.db)
    AGENT_VERSION a specific version number to pin to, skipping any
                  deployment; the deployed version if unset, or the
                  latest version if there is no deployment either
    VOICE         "on" (default) or "off"
"""

import json
import os
import ssl

from livekit import agents
from livekit.agents import (
    Agent, AgentServer, AgentSession, JobProcess, inference, room_io,
)
from livekit.plugins import google, silero

from voicelab import config, cost, registry, runlog
from voicelab.tool_factory import build_tools
from voicelab.trace import trace_session

AGENT_NAME = os.environ.get("AGENT_NAME", "dynabook")
AGENT_ORG = os.environ.get("AGENT_ORG", "default")
AGENT_DB = os.environ.get("AGENT_DB", "runs/registry.db")
AGENT_VERSION = os.environ.get("AGENT_VERSION")
STREAM_STT_MODEL = os.environ.get(
    "STREAM_STT_MODEL", "gemini-3.5-transcribe-live"
)
TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-2.5-flash-preview-tts")
VAD_SILENCE = float(os.environ.get("VAD_SILENCE", "1.2"))
VOICE = os.environ.get("VOICE", "on")


def prewarm(proc: JobProcess) -> None:
    """Chapter 35: pays the cold-start cost Chapter 34 disclosed once,
    per idle process, before any job is assigned to it, instead of
    once per call. `google.LLM` and `google.beta.GeminiTTS` build a
    `google.genai.Client` in their own `__init__` and keep it for the
    object's life, so building one of each here and reusing the same
    instance in every job this process ever runs skips the repeat
    construction entirely. `silero.VAD.load` builds an onnxruntime
    inference session the same way, on the same worker's own
    evidence from this OCI box, not the SSL cost Chapter 34 measured
    on a different machine.

    `google.beta.GeminiSTT` does not get the same fix: its vendored
    `RecognizeStream._run` builds a fresh `genai.Client` on every
    stream, including a mid-call reconnect, with no constructor
    argument to inject an existing one. `ssl.create_default_context`
    is called here anyway, once, on the chance that it warms
    something at the OS level a fresh call in this process can reuse;
    Chapter 35's own measurement is what decides whether that helps,
    not this comment.
    """
    key = config.gemini_key()
    ssl.create_default_context()
    proc.userdata["gemini_key"] = key
    proc.userdata["llm_cache"] = {}
    proc.userdata["tts"] = (
        google.beta.GeminiTTS(model=TTS_MODEL, voice_name="Puck",
                              api_key=key) if VOICE == "on" else None
    )
    proc.userdata["vad"] = silero.VAD.load(min_silence_duration=VAD_SILENCE)


server = AgentServer(
    load_threshold=0.95, num_idle_processes=2,
    initialize_process_timeout=60.0, port=0,
    setup_fnc=prewarm,
)


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: agents.JobContext):
    metadata = json.loads(ctx.job.metadata or "{}")
    run_dir = metadata.get("run_dir", "runs/mine")
    org = metadata.get("org_id", AGENT_ORG)
    stages = f"{run_dir}/stages.jsonl"
    ledger_path = os.environ.get("LEDGER", f"{run_dir}/ledger.jsonl")

    if AGENT_VERSION:
        version = registry.get_version(AGENT_DB, org, AGENT_NAME,
                                        int(AGENT_VERSION))
        lane = "pinned"
    else:
        deployment = registry.current_deployment(AGENT_DB, org, AGENT_NAME)
        if deployment is None:
            version = registry.get_version(AGENT_DB, org, AGENT_NAME)
            lane = "latest"
        else:
            version_number, lane = registry.choose_version(deployment)
            version = registry.get_version(AGENT_DB, org, AGENT_NAME,
                                           version_number)
    if version is None:
        raise RuntimeError(
            f"no version of {org}/{AGENT_NAME} in {AGENT_DB!r} to run"
        )

    key = ctx.proc.userdata.get("gemini_key") or config.gemini_key()
    llm_cache = ctx.proc.userdata.setdefault("llm_cache", {})
    if version.model not in llm_cache:
        llm_cache[version.model] = google.LLM(
            model=version.model, api_key=key,
            thinking_config={"thinking_level": "low"},
        )
    runlog.append(stages, {
        "stage": "config", "room": ctx.room.name, "org_id": org,
        "lane": lane, "agent_version": version.version, "llm": version.model,
        "tools": version.tools, "ledger": ledger_path, "voice": VOICE,
    })

    try:
        tools = build_tools(version.tools, ledger_path, ctx.room,
                           stages)
    except ValueError as exc:
        runlog.append(stages, {
            "stage": "worker_error", "room": ctx.room.name, "lane": lane,
            "agent_version": version.version, "error": str(exc),
        })
        raise

    session = AgentSession(
        stt=google.beta.GeminiSTT(model=STREAM_STT_MODEL, api_key=key),
        llm=llm_cache[version.model],
        tts=ctx.proc.userdata.get("tts") if VOICE == "on" else None,
        vad=ctx.proc.userdata["vad"],
        turn_handling={"turn_detection": inference.TurnDetector(
            version="v1-mini")},
    )

    async def log_usage():
        cost.record(session, stages)

    ctx.add_shutdown_callback(log_usage)
    trace_session(session, stages, ctx.room.name)

    await session.start(
        room=ctx.room,
        agent=Agent(instructions=version.instructions, tools=tools),
        room_options=room_io.RoomOptions(audio_output=VOICE == "on"),
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
