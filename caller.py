"""A synthetic caller that measures time to first audio (TTFA).

For each call it joins a fresh room on the local LiveKit server, asks an
agent to join, plays a recorded question in real time, then waits for the
agent to answer. TTFA is the time from the end of the caller's speech to the
first agent audio frame loud enough to hear.

    uv run caller.py --agent realtime --calls 10 --run runs/mine-realtime

Each call becomes one line in <run>/trials.jsonl. The agent writes its own
stage timings to <run>/stages.jsonl.
"""

import argparse
import asyncio
import json
import time
import uuid
import wave

import numpy as np
from livekit import api, rtc

from voicelab import config, runlog

QUESTION = "audio/refund_question.wav"
AUDIBLE_RMS = 300  # int16 loudness above this counts as the agent speaking
AGENT_RATE = 24000  # sample rate we ask for when listening to the agent
SILENCE_AFTER_S = 12.0  # keep the line open this long after the question
JOIN_TIMEOUT_S = 40.0


def read_question(path: str) -> tuple[int, np.ndarray]:
    with wave.open(path, "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        return w.getframerate(), pcm


def loudness(frame: rtc.AudioFrame) -> float:
    samples = np.frombuffer(frame.data, dtype=np.int16).astype(np.float64)
    return float(np.sqrt(np.mean(samples**2))) if samples.size else 0.0


async def pace(started: float, frames_sent: int) -> None:
    """Sleep until the next 10 ms frame is due.

    Sending on a real-time schedule matters twice: the agent hears speech
    at normal speed, and the pause gives the listening task a turn to
    record the moment the agent's first audio arrives.
    """
    due = started + frames_sent * 0.01
    await asyncio.sleep(max(0.0, due - time.monotonic()))


async def one_call(number: int, agent: str, run_dir: str) -> dict:
    rate, pcm = read_question(QUESTION)
    room_name = f"call-{uuid.uuid4().hex[:8]}"
    token = (
        api.AccessToken(config.LIVEKIT_API_KEY, config.LIVEKIT_API_SECRET)
        .with_identity("caller")
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )
    room = rtc.Room()
    heard = {"task": None, "first_audio": None, "audio_s": 0.0}
    speech_end = {"t": None}

    async def listen(track):
        stream = rtc.AudioStream(
            track, sample_rate=AGENT_RATE, num_channels=1
        )
        async for event in stream:
            if loudness(event.frame) > AUDIBLE_RMS:
                seconds = event.frame.samples_per_channel / AGENT_RATE
                heard["audio_s"] += seconds
                if speech_end["t"] and heard["first_audio"] is None:
                    heard["first_audio"] = time.monotonic()

    @room.on("track_subscribed")
    def on_track(track, publication, participant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            heard["task"] = asyncio.create_task(listen(track))

    result = {"call": number, "agent": agent, "room": room_name, "ok": False}
    http_url = config.LIVEKIT_URL.replace("ws", "http", 1)
    lk = api.LiveKitAPI(
        http_url, config.LIVEKIT_API_KEY, config.LIVEKIT_API_SECRET
    )
    try:
        await room.connect(config.LIVEKIT_URL, token)
        source = rtc.AudioSource(rate, 1)
        mic = rtc.LocalAudioTrack.create_audio_track("caller-mic", source)
        await room.local_participant.publish_track(
            mic,
            rtc.TrackPublishOptions(
                source=rtc.TrackSource.SOURCE_MICROPHONE
            ),
        )
        dispatched = time.monotonic()
        request = api.CreateAgentDispatchRequest(
            agent_name=agent,
            room=room_name,
            metadata=json.dumps({"run_dir": run_dir}),
        )
        await lk.agent_dispatch.create_dispatch(request)
        while heard["task"] is None:
            if time.monotonic() - dispatched > JOIN_TIMEOUT_S:
                result["error"] = "agent did not join"
                return result
            await asyncio.sleep(0.1)
        result["join_s"] = round(time.monotonic() - dispatched, 3)
        await asyncio.sleep(1.0)  # let the agent's session settle

        step = rate // 100  # one frame is 10 ms of audio
        started = time.monotonic()
        for n, i in enumerate(range(0, len(pcm), step)):
            chunk = pcm[i : i + step]
            frame = rtc.AudioFrame.create(rate, 1, step)
            samples = np.frombuffer(frame.data, dtype=np.int16)
            samples[:] = np.pad(chunk, (0, step - len(chunk)))
            await source.capture_frame(frame)
            await pace(started, n + 1)
        await source.wait_for_playout()
        speech_end["t"] = time.monotonic()
        result["speech_end_wall"] = round(time.time(), 3)
        result["question_s"] = round(speech_end["t"] - started, 3)

        silence = rtc.AudioFrame.create(rate, 1, step)
        n = 0
        while time.monotonic() < speech_end["t"] + SILENCE_AFTER_S:
            await source.capture_frame(silence)
            n += 1
            await pace(speech_end["t"], n)

        if heard["first_audio"] is None:
            result["error"] = "no audible answer"
        else:
            result["ok"] = True
            waited = heard["first_audio"] - speech_end["t"]
            result["ttfa_s"] = round(waited, 3)
            result["answer_audio_s"] = round(heard["audio_s"], 2)
        return result
    finally:
        if heard["task"] is not None:
            heard["task"].cancel()
        await room.disconnect()
        await lk.aclose()


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agent", required=True, help="realtime or cascaded")
    parser.add_argument("--calls", type=int, default=1)
    parser.add_argument("--run", required=True, help="run directory")
    args = parser.parse_args()
    for number in range(1, args.calls + 1):
        result = await one_call(number, args.agent, args.run)
        print(json.dumps(result))
        runlog.append(f"{args.run}/trials.jsonl", result)
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
