"""Chapter 3: an "agent" that only sends back what it hears. No model, no key.

    uv run echo_agent.py start

With no model in the loop, the delay between the caller starting to speak
and hearing its own voice come back is the transport alone: the network
path, the codec and the buffers, there and back.
"""

import asyncio

from livekit import agents, rtc
from livekit.agents import AgentServer

from voicelab import config  # noqa: F401  (sets the local server defaults)

# port=0 lets it run next to another agent, which already uses port 8081
# for its health check.
server = AgentServer(
    load_threshold=0.95,
    num_idle_processes=2,
    initialize_process_timeout=60.0,
    port=0,
)


@server.rtc_session(agent_name="echo")
async def entrypoint(ctx: agents.JobContext):
    source = rtc.AudioSource(48000, 1)
    started = set()

    async def echo(remote: rtc.Track) -> None:
        stream = rtc.AudioStream(remote, sample_rate=48000, num_channels=1)
        async for event in stream:
            await source.capture_frame(event.frame)

    def start_echo(remote: rtc.Track) -> None:
        if remote.kind != rtc.TrackKind.KIND_AUDIO or remote.sid in started:
            return
        started.add(remote.sid)
        asyncio.create_task(echo(remote))

    # Listen before connecting: a caller that published its microphone
    # before the agent joined is subscribed during connect().
    @ctx.room.on("track_subscribed")
    def on_track(remote, publication, participant):
        start_echo(remote)

    await ctx.connect()
    track = rtc.LocalAudioTrack.create_audio_track("echo", source)
    await ctx.room.local_participant.publish_track(track)
    for participant in ctx.room.remote_participants.values():
        for publication in participant.track_publications.values():
            if publication.track is not None:
                start_echo(publication.track)


if __name__ == "__main__":
    agents.cli.run_app(server)
