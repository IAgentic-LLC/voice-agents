"""Chapter 7: an agent that talks, so it can be interrupted.

It says one recorded answer and nothing else. There is no model and no
speech service, so a barge-in run costs nothing and plays the same audio
every time. The interruption machinery is the real one.

    uv run talker_agent.py start

Settings (environment variables):
    AGENT_NAME    the name callers ask for (default "talker")
    VAD_SILENCE   seconds of silence before the voice detector ends a
                  stretch of speech (default 1.2, long enough that the
                  pause in the recorded question does not split it)
    MIN_DURATION  how long the caller must speak before it counts as an
                  interruption, in seconds (LiveKit's default is 0.5)
    INTERRUPT     "on" (default) or "off": off makes the answer
                  uninterruptible, so a caller has to talk over it
    RESUME        "on" (default) or "off": whether the agent picks the
                  answer up again after a false interruption
    FALSE_TIMEOUT seconds of silence after an interruption before it is
                  called false (LiveKit's default is 2.0)
    MIN_WORDS     how many words the caller must say before it counts as
                  an interruption (LiveKit's default is 0, which needs no
                  transcription); anything above 0 turns transcription on
    ANSWER        the recording to play (default audio/agent_answer.wav)

Timings go to <run dir>/stages.jsonl, as in every other chapter.
"""

import asyncio
import json
import os
import time

import numpy as np
from livekit import agents, rtc
from livekit.agents import Agent, AgentServer, AgentSession, room_io
from livekit.plugins import google, silero

from voicelab import config, runlog
from voicelab.audio import read_wav
from voicelab.trace import trace_session

AGENT_NAME = os.environ.get("AGENT_NAME", "talker")
VAD_SILENCE = float(os.environ.get("VAD_SILENCE", "1.2"))
ANSWER = os.environ.get("ANSWER", "audio/agent_answer.wav")
INTERRUPT = os.environ.get("INTERRUPT", "on")
RESUME = os.environ.get("RESUME", "on")
INTERRUPTION = {
    "enabled": INTERRUPT == "on",
    "resume_false_interruption": RESUME == "on",
}
if "MIN_DURATION" in os.environ:
    INTERRUPTION["min_duration"] = float(os.environ["MIN_DURATION"])
MIN_WORDS = int(os.environ.get("MIN_WORDS", "0"))
if MIN_WORDS:
    INTERRUPTION["min_words"] = MIN_WORDS
if "FALSE_TIMEOUT" in os.environ:
    INTERRUPTION["false_interruption_timeout"] = float(
        os.environ["FALSE_TIMEOUT"]
    )


async def play(pcm: np.ndarray, rate: int, stages: str, room: str):
    """The answer, 10 ms at a time, with a note of each frame handed over.

    Frames are produced as fast as they are taken. What stops this
    generator is the session cancelling it, which is the moment the agent
    decides to stop talking.
    """
    step = rate // 100
    sent = 0
    try:
        for i in range(0, len(pcm), step):
            chunk = pcm[i : i + step]
            frame = rtc.AudioFrame.create(rate, 1, step)
            np.frombuffer(frame.data, dtype=np.int16)[:] = np.pad(
                chunk, (0, step - len(chunk))
            )
            yield frame
            sent += 1
    finally:
        runlog.append(stages, {
            "stage": "trace", "room": room, "event": "answer frames sent",
            "at": time.time(), "seconds": round(sent * step / rate, 3),
            "whole": sent * step >= len(pcm),
        })


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
    pcm, rate = read_wav(ANSWER)
    runlog.append(stages, {
        "stage": "config", "answer": ANSWER,
        "answer_s": round(len(pcm) / rate, 3), "vad_silence": VAD_SILENCE,
        "min_words": MIN_WORDS,
        "interruption": INTERRUPTION,
    })

    # Counting the caller's words means transcribing them, so a word
    # threshold is the one setting here that costs money.
    session = AgentSession(
        stt=google.beta.GeminiSTT(
            model="gemini-3.5-transcribe-live", api_key=config.gemini_key()
        ) if MIN_WORDS else None,
        vad=silero.VAD.load(min_silence_duration=VAD_SILENCE),
        turn_handling={"turn_detection": "vad",
                       "interruption": INTERRUPTION},
    )
    runlog.append(stages, {
        "stage": "config", "resolved": dict(session.options.interruption),
    })
    trace_session(session, stages, ctx.room.name)

    @session.on("speech_created")
    def on_speech(ev):
        runlog.append(stages, {
            "stage": "trace", "room": ctx.room.name,
            "event": "speech created", "at": time.time(),
        })

    await session.start(
        room=ctx.room,
        agent=Agent(instructions="Play one recorded answer."),
        room_options=room_io.RoomOptions(audio_output=True),
    )

    # Wait for the caller to finish the question, then answer. Starting
    # while the caller is still speaking would be interrupted at once, so
    # the answer waits for a quarter second of continued quiet as well.
    state = {"user": "listening", "asked": False, "quiet_since": None}

    @session.on("user_state_changed")
    def on_user(ev):
        state["user"] = ev.new_state
        if ev.new_state == "speaking":
            state["asked"] = True
            state["quiet_since"] = None
        elif state["asked"]:
            state["quiet_since"] = time.time()

    while not (state["quiet_since"]
               and time.time() - state["quiet_since"] > 0.25):
        await asyncio.sleep(0.05)
    handle = session.say(
        "the recorded answer",
        audio=play(pcm, rate, stages, ctx.room.name),
        add_to_chat_ctx=False,
    )
    await handle
    runlog.append(stages, {
        "stage": "trace", "room": ctx.room.name, "event": "answer finished",
        "at": time.time(), "interrupted": handle.interrupted,
    })


if __name__ == "__main__":
    agents.cli.run_app(server)
