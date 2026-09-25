"""A synthetic caller that measures time to first audio (TTFA).

For each call it joins a fresh room on the local LiveKit server, asks an
agent to join, plays a recorded question in real time, then waits for the
agent to answer. TTFA is the time from the end of the caller's speech (the
last loud frame of the question, not the end of the file) to the first
agent audio frame loud enough to hear.

    uv run caller.py --agent realtime --calls 10 --run runs/mine-realtime

With --interrupt it also talks over the answer, and measures how long the
agent keeps speaking afterwards (Chapter 7).

Each call becomes one line in <run>/trials.jsonl. The agent writes its own
stage timings to <run>/stages.jsonl.
"""

import argparse
import asyncio
import json
import time
import uuid

import numpy as np
from livekit import api, rtc

from voicelab import config, runlog
from voicelab.question import (
    AUDIBLE_RMS, QUESTION, read_question, speech_end_s,
)

AGENT_RATE = 24000  # sample rate we ask for when listening to the agent
SILENCE_AFTER_S = 12.0  # keep the line open this long after the question
JOIN_TIMEOUT_S = 40.0
FAINT_RMS = 10  # any sound at all, far below the audible threshold


def loudness_of(samples: np.ndarray) -> float:
    samples = samples.astype(np.float64)
    return float(np.sqrt(np.mean(samples**2))) if samples.size else 0.0


def loudness(frame: rtc.AudioFrame) -> float:
    return loudness_of(np.frombuffer(frame.data, dtype=np.int16))


async def pace(started: float, frames_sent: int) -> None:
    """Sleep until the next 10 ms frame is due, so the agent hears the
    question at normal speed and the caller knows when each frame went out.
    """
    due = started + frames_sent * 0.01
    await asyncio.sleep(max(0.0, due - time.monotonic()))


async def one_call(
    number: int, agent: str, run_dir: str, question: str = QUESTION,
    interrupt: str | None = None, after: float = 2.0,
    listen_s: float = SILENCE_AFTER_S, hangup_s: float | None = None,
    at_s: float | None = None, org: str | None = None,
) -> dict:
    rate, pcm = read_question(question)
    room_name = f"call-{uuid.uuid4().hex[:8]}"
    token = (
        api.AccessToken(config.LIVEKIT_API_KEY, config.LIVEKIT_API_SECRET)
        .with_identity("caller")
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )
    room = rtc.Room()
    heard = {"task": None, "first_audio": None, "audio_s": 0.0,
             "first_any": None, "audio_after_s": 0.0, "gaps": [],
             "quiet": []}
    speech_end = {"t": None}
    barge = {"t": None}  # when the interruption's first loud frame went out

    async def listen(track):
        stream = rtc.AudioStream(
            track, sample_rate=AGENT_RATE, num_channels=1
        )
        async for event in stream:
            # Chapter 4: also note the first frame with any sound in it,
            # well below the threshold for "audible".
            if (speech_end["t"] and "first_any_wall" not in heard
                    and loudness(event.frame) > FAINT_RMS):
                heard["first_any_wall"] = time.time()
            if loudness(event.frame) > AUDIBLE_RMS:
                seconds = event.frame.samples_per_channel / AGENT_RATE
                heard["audio_s"] += seconds
                # Chapter 7: the agent's audio after the caller cut in,
                # and the gap that shows it started again.
                now = time.time()
                # Chapter 10: every silence in what the agent says, so a
                # run can be asked how long the caller waited with
                # nothing to listen to.
                quiet = now - heard.get("last_audio_wall", now)
                if quiet > 0.4 and heard["first_audio"] is not None:
                    heard["quiet"].append(round(quiet, 3))
                if barge["t"] is not None and now > barge["t"]:
                    heard["audio_after_s"] += seconds
                    # Every silence in the agent's audio after the
                    # interruption. The recorded answer has its own
                    # pauses, the longest 0.62 s, so what counts as the
                    # agent having stopped and started again is decided
                    # when the run is read, not here.
                    gap = now - heard.get("last_audio_wall", now)
                    if gap > 0.4:
                        heard["gaps"].append(
                            (round(heard["last_audio_wall"] - barge["t"], 3),
                             round(gap, 3))
                        )
                heard["last_audio_wall"] = now
                if heard["first_any"] is None:
                    heard["first_any"] = time.monotonic()
                if speech_end["t"] and heard["first_audio"] is None:
                    heard["first_audio"] = time.monotonic()
                    heard["first_audio_wall"] = time.time()

    @room.on("track_subscribed")
    def on_track(track, publication, participant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            heard["task"] = asyncio.create_task(listen(track))

    # An agent with its voice off (Chapter 6) publishes no audio track, so
    # count it as joined when it enters the room.
    @room.on("participant_connected")
    def on_join(participant):
        heard["joined"] = True

    result = {"call": number, "agent": agent, "room": room_name, "ok": False,
              "question": question}
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
        metadata = {"run_dir": run_dir}
        if org is not None:
            metadata["org_id"] = org
        request = api.CreateAgentDispatchRequest(
            agent_name=agent,
            room=room_name,
            metadata=json.dumps(metadata),
        )
        await lk.agent_dispatch.create_dispatch(request)
        while heard["task"] is None and not heard.get("joined"):
            if time.monotonic() - dispatched > JOIN_TIMEOUT_S:
                result["error"] = "agent did not join"
                return result
            await asyncio.sleep(0.1)
        result["join_s"] = round(time.monotonic() - dispatched, 3)
        await asyncio.sleep(1.0)  # let the agent's session settle

        step = rate // 100  # one frame is 10 ms of audio
        last_loud = round(speech_end_s(question) * rate)  # speech ends here
        # When the first loud frame goes out, for the echo delay (Chapter 3).
        loud_at = next(i for i in range(0, len(pcm), step)
                       if loudness_of(pcm[i : i + step]) > AUDIBLE_RMS)
        started = time.monotonic()
        for n, i in enumerate(range(0, len(pcm), step)):
            chunk = pcm[i : i + step]
            frame = rtc.AudioFrame.create(rate, 1, step)
            samples = np.frombuffer(frame.data, dtype=np.int16)
            samples[:] = np.pad(chunk, (0, step - len(chunk)))
            await source.capture_frame(frame)
            await pace(started, n + 1)
            if speech_end["t"] is None and i + step >= last_loud:
                # The last loud frame has gone out: the caller has stopped
                # speaking. The rest of the file is quiet room tone.
                speech_end["t"] = time.monotonic()
                result["speech_end_wall"] = round(time.time(), 4)
        await source.wait_for_playout()
        result["question_s"] = round(time.monotonic() - started, 3)

        silence = rtc.AudioFrame.create(rate, 1, step)
        cut_in = None  # frames of the interruption, once it is due
        if interrupt:
            cut_rate, cut_pcm = read_question(interrupt)
            if cut_rate != rate:
                raise SystemExit(
                    f"{interrupt} is {cut_rate} Hz, the question is {rate}"
                )
            cut_loud = next(i for i in range(0, len(cut_pcm), step)
                            if loudness_of(cut_pcm[i : i + step])
                            > AUDIBLE_RMS)
        # Chapter 10: hanging up is just leaving early.
        leave_at = speech_end["t"] + (listen_s if hangup_s is None
                                      else hangup_s)
        if hangup_s is not None:
            result["hung_up_after_s"] = hangup_s
        tail_started, n, played = time.monotonic(), 0, 0
        while time.monotonic() < leave_at:
            frame = silence
            # The caller speaks again either once the agent has been
            # talking for `after` seconds, or at a fixed moment after its
            # own question, which is the only way to talk over an agent
            # that is not making any sound yet (Chapter 10).
            due = (at_s is not None
                   and time.monotonic() > speech_end["t"] + at_s)
            if not due:
                due = (at_s is None and heard["first_audio"] is not None
                       and time.monotonic() > heard["first_audio"] + after)
            if interrupt and cut_in is None and due:
                cut_in = 0
            if cut_in is not None and cut_in < len(cut_pcm):
                chunk = cut_pcm[cut_in : cut_in + step]
                frame = rtc.AudioFrame.create(rate, 1, step)
                np.frombuffer(frame.data, dtype=np.int16)[:] = np.pad(
                    chunk, (0, step - len(chunk))
                )
                if barge["t"] is None and cut_in + step > cut_loud:
                    barge["t"] = time.time()
                    result["interrupt_start_wall"] = round(barge["t"], 4)
                cut_in += step
                played += step
            await source.capture_frame(frame)
            n += 1
            await pace(tail_started, n)
        if interrupt:
            result["interrupt"] = interrupt
            if at_s is None:
                result["interrupt_after_s"] = after
            else:
                result["interrupt_at_s"] = at_s
            if barge["t"] is not None and "last_audio_wall" in heard:
                result["agent_stopped_wall"] = round(
                    heard["last_audio_wall"], 4
                )
                result["stop_s"] = round(
                    heard["last_audio_wall"] - barge["t"], 3
                )
                result["heard_after_s"] = round(heard["audio_after_s"], 3)
                result["gaps"] = heard["gaps"]

        if agent == "echo" and heard["first_any"] is not None:
            sent = started + (loud_at // step) * 0.01
            result["ok"] = True
            result["echo_delay_s"] = round(heard["first_any"] - sent, 3)
            return result
        result["t0"] = "speech_end"  # the waits below count from here
        if heard["first_audio"] is None:
            result["error"] = "no audible answer"
        else:
            result["ok"] = True
            waited = heard["first_audio"] - speech_end["t"]
            result["ttfa_s"] = round(waited, 3)
            result["first_audio_wall"] = round(heard["first_audio_wall"], 4)
            if "first_any_wall" in heard:
                result["first_any_wall"] = round(heard["first_any_wall"], 4)
            result["answer_audio_s"] = round(heard["audio_s"], 2)
        if heard["quiet"]:
            result["quiet_s"] = heard["quiet"]
        return result
    finally:
        if heard["task"] is not None:
            heard["task"].cancel()
        await room.disconnect()
        await lk.aclose()


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agent", required=True,
                        help="the agent's name, such as realtime or cascaded")
    parser.add_argument("--calls", type=int, default=1)
    parser.add_argument("--run", required=True, help="run directory")
    parser.add_argument("--question", default=QUESTION,
                        help="the recording to play (Chapter 6)")
    parser.add_argument("--interrupt",
                        help="a recording to talk over the answer with "
                             "(Chapter 7)")
    parser.add_argument("--after", type=float, default=2.0,
                        help="seconds of the answer to let through first")
    parser.add_argument("--listen", type=float, default=SILENCE_AFTER_S,
                        help="seconds to keep the line open after the "
                             "question")
    parser.add_argument("--interrupt-at", type=float, dest="at",
                        help="say it this many seconds after the question "
                             "instead, whether or not the agent is talking")
    parser.add_argument("--hangup", type=float,
                        help="leave the call this many seconds after the "
                             "question, mid-answer (Chapter 10)")
    args = parser.parse_args()
    for number in range(1, args.calls + 1):
        result = await one_call(number, args.agent, args.run, args.question,
                                args.interrupt, args.after, args.listen,
                                args.hangup, args.at)
        print(json.dumps(result))
        runlog.append(f"{args.run}/trials.jsonl", result)
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
