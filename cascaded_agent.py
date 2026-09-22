"""Cascaded voice agent: speech to text, then a text model, then speech.

Start it and leave it running while caller.py places calls:

    uv run cascaded_agent.py start

Settings (environment variables):
    VAD_SILENCE   seconds of silence before the voice detector ends a
                  stretch of speech (default 0.55, Silero's own default)
    STT_MODE      "batch": send each stretch of speech to a Gemini model
                  once it ends (default); "stream": transcribe while the
                  caller speaks (Chapter 5)
    AGENT_NAME    the name callers ask for (default "cascaded"), so two
                  versions can run side by side (Chapter 5)
    TURN          "detector": LiveKit's turn detector decides when a turn
                  ends (default, as in every earlier chapter); "vad":
                  silence alone decides (Chapter 6)
    MIN_DELAY, MAX_DELAY
                  the short and long waits the turn detector chooses
                  between, in seconds (LiveKit's defaults if unset)
    VOICE         "on" (default) or "off": off skips the voice entirely, for
                  experiments that only measure turn taking (Chapter 6)

Timings from every stage go to <run dir>/stages.jsonl.
"""

import json
import os
import time
import uuid

from google import genai
from google.genai import types
from livekit import agents, rtc
from livekit.agents import (
    Agent, AgentServer, AgentSession, inference, room_io, stt, utils,
)
from livekit.agents.types import NOT_GIVEN, APIConnectOptions, NotGivenOr
from livekit.plugins import google, silero

from voicelab import config, cost, policy, runlog
from voicelab.trace import trace_session

LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")
STT_MODEL = os.environ.get("STT_MODEL", "gemini-3.5-flash-lite")
STREAM_STT_MODEL = os.environ.get(
    "STREAM_STT_MODEL", "gemini-3.5-transcribe-live"
)
# 2.5 Flash TTS: half the audio price of 3.1, and its own daily request
# quota (the key used for the book allowed 100 requests a day per model).
TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-2.5-flash-preview-tts")
VAD_SILENCE = float(os.environ.get("VAD_SILENCE", "0.55"))
STT_MODE = os.environ.get("STT_MODE", "batch")
AGENT_NAME = os.environ.get("AGENT_NAME", "cascaded")
TURN = os.environ.get("TURN", "detector")
VOICE = os.environ.get("VOICE", "on")
ENDPOINTING = {
    key: float(os.environ[env])
    for key, env in (("min_delay", "MIN_DELAY"), ("max_delay", "MAX_DELAY"))
    if env in os.environ
}
# Some Gemini models reject "minimal"; "low" used no thinking tokens here.
THINKING = os.environ.get("THINKING_LEVEL", "low")

# Chapter 8 gives both agents the same policy to answer from, so their
# answers can be scored against the same facts. PROMPT=plain is what
# every earlier chapter used.
INSTRUCTIONS = (
    policy.INSTRUCTIONS if os.environ.get("PROMPT") == "policy"
    else "You are a concise customer support assistant. "
         "Answer in one or two short sentences."
)
TRANSCRIBE = "Transcribe this audio word for word. Output only the words."


class BatchSTT(stt.STT):
    """Transcribe one finished stretch of speech with a Gemini model."""

    def __init__(self, *, api_key: str, model: str, stages: str) -> None:
        super().__init__(
            capabilities=stt.STTCapabilities(
                streaming=False, interim_results=False
            )
        )
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._stages = stages

    @property
    def model(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return "gemini-batch"

    async def _recognize_impl(
        self,
        buffer: utils.AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions,
    ) -> stt.SpeechEvent:
        frame = rtc.combine_audio_frames(buffer)
        started = time.monotonic()
        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=[
                types.Part.from_bytes(
                    data=frame.to_wav_bytes(), mime_type="audio/wav"
                ),
                TRANSCRIBE,
            ],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level=THINKING)
            ),
        )
        text = (resp.text or "").strip()
        runlog.append(self._stages, {
            "stage": "stt",
            "audio_s": round(
                frame.samples_per_channel / frame.sample_rate, 2
            ),
            "stt_s": round(time.monotonic() - started, 3),
            "text": text,
        })
        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            request_id=uuid.uuid4().hex,
            alternatives=[stt.SpeechData(language="en", text=text)],
        )


# Local-machine settings. The default CPU threshold (0.7) made a busy laptop
# refuse calls, and a fresh install on Windows can take longer than the
# default 10 s to start a worker process.
server = AgentServer(
    load_threshold=0.95,
    num_idle_processes=2,
    initialize_process_timeout=60.0,
    port=0,  # any free port, so two agents can run side by side
)


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: agents.JobContext):
    metadata = json.loads(ctx.job.metadata or "{}")
    run_dir = metadata.get("run_dir", "runs/mine")
    stages = f"{run_dir}/stages.jsonl"
    key = config.gemini_key()
    runlog.append(stages, {
        "stage": "config", "llm": LLM_MODEL, "tts": TTS_MODEL,
        "stt_mode": STT_MODE, "vad_silence": VAD_SILENCE,
        "stt": STREAM_STT_MODEL if STT_MODE == "stream" else STT_MODEL,
        "turn": TURN, "endpointing": ENDPOINTING, "voice": VOICE,
    })

    vad = silero.VAD.load(min_silence_duration=VAD_SILENCE)
    if STT_MODE == "stream":
        speech_to_text = google.beta.GeminiSTT(
            model=STREAM_STT_MODEL, api_key=key
        )
    else:
        batch = BatchSTT(api_key=key, model=STT_MODEL, stages=stages)
        speech_to_text = stt.StreamAdapter(stt=batch, vad=vad)

    session = AgentSession(
        stt=speech_to_text,
        llm=google.LLM(
            model=LLM_MODEL,
            api_key=key,
            thinking_config={"thinking_level": THINKING},
        ),
        tts=google.beta.GeminiTTS(
            model=TTS_MODEL, voice_name="Puck", api_key=key
        ) if VOICE == "on" else None,
        vad=vad,
        turn_handling={
            "turn_detection": "vad" if TURN == "vad"
            else inference.TurnDetector(version="v1-mini"),
            **({"endpointing": ENDPOINTING} if ENDPOINTING else {}),
        },
    )

    @session.on("metrics_collected")
    def on_metrics(ev):
        metrics = json.loads(ev.metrics.model_dump_json())
        if metrics.get("type") != "vad_metrics":  # one per second, noise
            runlog.append(stages, {"stage": "metrics", "metrics": metrics})

    async def log_usage():
        cost.record(session, stages)  # Chapter 8

    ctx.add_shutdown_callback(log_usage)
    trace_session(session, stages, ctx.room.name)  # Chapter 4
    await session.start(
        room=ctx.room,
        agent=Agent(instructions=INSTRUCTIONS),
        room_options=room_io.RoomOptions(audio_output=VOICE == "on"),
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
