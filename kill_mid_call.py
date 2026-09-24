"""Chapter 29: what a caller's own room notices when the agent's
runtime is killed mid-call, with no chance to say goodbye.

This starts its own worker so the exact real process is never in
doubt, places one real call against it, waits until a fixed point
past the caller's question, then kills the worker one of two ways:

    uv run kill_mid_call.py --run runs/mine --kill-mode wrapper
    uv run kill_mid_call.py --run runs/mine --kill-mode tree

`wrapper` kills only the PID `subprocess.Popen` itself hands back,
the `uv run` process. `tree` kills that PID and every real process
descended from it, found with `psutil`, not guessed at.
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time

import numpy as np
import psutil
from livekit import api, rtc

from caller import pace
from voicelab import config, runlog
from voicelab.question import QUESTION, read_question

REGISTER_WAIT_S = 10.0
NOTICE_TIMEOUT_S = 60.0


def kill_worker(proc: subprocess.Popen, mode: str) -> list[int]:
    root = psutil.Process(proc.pid)
    targets = [root] if mode == "wrapper" else [
        root, *root.children(recursive=True)
    ]
    killed = []
    for p in targets:
        try:
            p.kill()
            killed.append(p.pid)
        except psutil.NoSuchProcess:
            pass
    return killed


async def run(agent_name: str, run_dir: str, kill_after_s: float,
             kill_mode: str) -> dict:
    stages = f"{run_dir}/stages.jsonl"
    worker = subprocess.Popen(
        ["uv", "run", "tools_agent.py", "start"],
        env={**os.environ, "AGENT_NAME": agent_name},
    )
    await asyncio.sleep(REGISTER_WAIT_S)

    rate, pcm = read_question(QUESTION)
    room_name = f"call-{agent_name}-kill"
    token = (
        api.AccessToken(config.LIVEKIT_API_KEY, config.LIVEKIT_API_SECRET)
        .with_identity("caller")
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )
    room = rtc.Room()
    noticed = {"at": None}

    @room.on("participant_disconnected")
    def on_gone(participant):
        if noticed["at"] is None:
            noticed["at"] = time.time()

    http_url = config.LIVEKIT_URL.replace("ws", "http", 1)
    lk = api.LiveKitAPI(
        http_url, config.LIVEKIT_API_KEY, config.LIVEKIT_API_SECRET
    )
    result = {"agent": agent_name, "room": room_name, "kill_mode": kill_mode}
    try:
        await room.connect(config.LIVEKIT_URL, token)
        source = rtc.AudioSource(rate, 1)
        mic = rtc.LocalAudioTrack.create_audio_track("caller-mic", source)
        await room.local_participant.publish_track(
            mic,
            rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE),
        )
        await lk.agent_dispatch.create_dispatch(api.CreateAgentDispatchRequest(
            agent_name=agent_name, room=room_name,
            metadata=json.dumps({"run_dir": run_dir}),
        ))
        await asyncio.sleep(4.0)

        step = rate // 100
        started = time.monotonic()
        for n, i in enumerate(range(0, len(pcm), step)):
            chunk = pcm[i : i + step]
            frame = rtc.AudioFrame.create(rate, 1, step)
            samples = np.frombuffer(frame.data, dtype=np.int16)
            samples[:] = np.pad(chunk, (0, step - len(chunk)))
            await source.capture_frame(frame)
            await pace(started, n + 1)
        await source.wait_for_playout()

        await asyncio.sleep(kill_after_s)
        kill_wall = time.time()
        result["killed_pids"] = kill_worker(worker, kill_mode)
        result["kill_wall"] = round(kill_wall, 4)

        waited = 0.0
        while noticed["at"] is None and waited < NOTICE_TIMEOUT_S:
            await asyncio.sleep(0.2)
            waited += 0.2
        result["disconnected_after_kill_s"] = (
            round(noticed["at"] - kill_wall, 3) if noticed["at"] else None
        )
        runlog.append(stages, {
            "stage": "trace", "room": room_name, "event": "kill result",
            "at": time.time(), **result,
        })
        return result
    finally:
        await room.disconnect()
        await lk.aclose()
        try:
            worker.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def main(agent_name: str, run_dir: str, kill_after_s: float,
        kill_mode: str) -> None:
    result = asyncio.run(run(agent_name, run_dir, kill_after_s, kill_mode))
    print(json.dumps(result))
    runlog.append(f"{run_dir}/trials.jsonl", result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agent", default="kmc")
    parser.add_argument("--run", required=True)
    parser.add_argument("--kill-after", type=float, default=3.0)
    parser.add_argument("--kill-mode", choices=["wrapper", "tree"],
                        required=True)
    args = parser.parse_args()
    main(args.agent, args.run, args.kill_after, args.kill_mode)
