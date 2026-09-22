"""Chapter 7: record one spoken line and keep it, so tests can be free.

    uv run say.py "text to speak" audio/agent_answer.wav [rate]

Sends one request to the Gemini speech model and writes the audio as a WAV
file. The recordings Chapter 7 plays, the agent's answer and the two lines
the caller interrupts with, were each made by one run of this script, so
the experiments that replay them cost nothing and give the same audio
every time. The question from Chapter 1 came from Windows' own speech
synthesis instead, and is kept as it is. Needs GEMINI_API_KEY.
"""

import asyncio
import sys
from pathlib import Path

import numpy as np
from livekit.plugins import google

from voicelab import config
from voicelab.audio import resample, write_wav

MODEL = "gemini-2.5-flash-preview-tts"
VOICE = "Puck"


async def record(text: str, path: str, rate_out: int = 0) -> None:
    speech = google.beta.GeminiTTS(
        model=MODEL, voice_name=VOICE, api_key=config.gemini_key()
    )
    chunks, rate = [], 24000
    stream = speech.synthesize(text)
    async for event in stream:
        frame = event.frame
        rate = frame.sample_rate
        chunks.append(np.frombuffer(frame.data, dtype=np.int16))
    await stream.aclose()
    pcm = np.concatenate(chunks)
    if rate_out and rate_out != rate:
        pcm, rate = resample(pcm, rate, rate_out), rate_out
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    write_wav(path, pcm, rate)
    print(f"wrote {path}  ({len(pcm) / rate:.2f} s at {rate} Hz)")


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        raise SystemExit(__doc__.splitlines()[2].strip())
    rate = int(sys.argv[3]) if len(sys.argv) == 4 else 0
    asyncio.run(record(sys.argv[1], sys.argv[2], rate))
