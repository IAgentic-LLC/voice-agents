"""Chapter 12: a caller whose connection drops, and who comes back.

    uv run reconnect.py --agent m12off --run runs/mine-drop \
      --first audio/ch09/plain.wav \
      --second audio/ch09/plain.wav --away 4

Joins a room, says the first thing, disconnects, waits, rejoins the same
room with the same identity, and says the second thing. What the agent
says next is the measurement: does it still know what it was told before
the line went?

Note what kind of drop this is. room.disconnect() is a deliberate leave,
which LiveKit reports as CLIENT_INITIATED, so this reproduces a hang-up
and a redial. A caller losing signal in a tunnel arrives as a different
reason (CONNECTION_TIMEOUT or SIGNAL_CLOSE), which is not in
DEFAULT_CLOSE_ON_DISCONNECT_REASONS and so would not close the session.

Everything is written to <run>/trials.jsonl, and the agent writes its
own side to <run>/stages.jsonl as usual.
"""

import argparse
import asyncio
import json
import time
import uuid

import numpy as np
from livekit import api, rtc

from voicelab import config, runlog
from voicelab.question import AUDIBLE_RMS, read_question

JOIN_TIMEOUT_S = 40.0


def token_for(room_name: str) -> str:
    return (
        api.AccessToken(config.LIVEKIT_API_KEY, config.LIVEKIT_API_SECRET)
        .with_identity("caller")  # the same person, both times
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )


async def say(room: rtc.Room, path: str) -> float:
    """Play a recording in real time. Returns when its last loud frame
    has gone out."""
    rate, pcm = read_question(path)
    source = rtc.AudioSource(rate, 1)
    track = rtc.LocalAudioTrack.create_audio_track("caller-mic", source)
    await room.local_participant.publish_track(
        track,
        rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE),
    )
    step = rate // 100
    started, last_loud = time.monotonic(), 0.0
    for n, i in enumerate(range(0, len(pcm), step)):
        chunk = pcm[i : i + step]
        frame = rtc.AudioFrame.create(rate, 1, step)
        np.frombuffer(frame.data, dtype=np.int16)[:] = np.pad(
            chunk, (0, step - len(chunk))
        )
        await source.capture_frame(frame)
        loud = np.sqrt(np.mean(chunk.astype(np.float64) ** 2))
        if loud > AUDIBLE_RMS:
            last_loud = time.time()
        await asyncio.sleep(
            max(0.0, started + (n + 1) * 0.01 - time.monotonic())
        )
    await source.wait_for_playout()
    return last_loud


async def one_call(agent: str, run_dir: str, first: str, second: str,
                   away_s: float, settle_s: float) -> dict:
    room_name = f"call-{uuid.uuid4().hex[:8]}"
    result = {"agent": agent, "room": room_name, "away_s": away_s,
              "first": first, "second": second}
    http = config.LIVEKIT_URL.replace("ws", "http", 1)
    lk = api.LiveKitAPI(http, config.LIVEKIT_API_KEY,
                        config.LIVEKIT_API_SECRET)
    room = rtc.Room()
    try:
        await room.connect(config.LIVEKIT_URL, token_for(room_name))
        await lk.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=agent, room=room_name,
                metadata=json.dumps({"run_dir": run_dir}),
            )
        )
        joined = time.monotonic()
        while not room.remote_participants:
            if time.monotonic() - joined > JOIN_TIMEOUT_S:
                result["error"] = "agent did not join"
                return result
            await asyncio.sleep(0.1)
        await asyncio.sleep(1.0)

        result["said_first_wall"] = round(await say(room, first), 4)
        await asyncio.sleep(settle_s)

        # The line drops. Nothing polite about it.
        await room.disconnect()
        result["dropped_wall"] = round(time.time(), 4)
        await asyncio.sleep(away_s)

        room = rtc.Room()
        await room.connect(config.LIVEKIT_URL, token_for(room_name))
        result["rejoined_wall"] = round(time.time(), 4)
        result["agent_still_there"] = bool(room.remote_participants)
        await asyncio.sleep(1.0)

        result["said_second_wall"] = round(await say(room, second), 4)
        await asyncio.sleep(settle_s)
        result["ok"] = True
        return result
    finally:
        await room.disconnect()
        await lk.aclose()


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agent", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--first", required=True)
    parser.add_argument("--second", required=True)
    parser.add_argument("--away", type=float, default=4.0,
                        help="seconds off the call before rejoining")
    parser.add_argument("--settle", type=float, default=9.0,
                        help="seconds to let the agent answer each time")
    parser.add_argument("--calls", type=int, default=1)
    args = parser.parse_args()
    for _ in range(args.calls):
        result = await one_call(args.agent, args.run, args.first,
                                args.second, args.away, args.settle)
        print(json.dumps(result))
        runlog.append(f"{args.run}/trials.jsonl", result)
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
