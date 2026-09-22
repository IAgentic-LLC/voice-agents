"""Chapter 2: make versions of the question and a test tone, and inspect them.

    uv run audio_lab.py make      # write the files to audio/ch02/
    uv run audio_lab.py inspect   # print what each file contains

Needs no key and no server. Listen to the files in audio/ch02/ with any
audio player.
"""

import sys
from pathlib import Path

from voicelab.audio import (
    dominant_frequency,
    energy_above,
    mulaw_roundtrip,
    naive_downsample,
    read_wav,
    resample,
    rms,
    tone,
    write_wav,
)

OUT = Path("audio/ch02")
QUESTION = "audio/refund_question.wav"


def make() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pcm, rate = read_wav(QUESTION)  # 16,000 samples a second
    # Same samples, wrong label: a player will run them too fast or too slow.
    write_wav(OUT / "question-labelled-24k.wav", pcm, 24000)
    write_wav(OUT / "question-labelled-8k.wav", pcm, 8000)
    # Down to telephone rate, two ways.
    write_wav(OUT / "question-8k-naive.wav", naive_downsample(pcm, 2), 8000)
    phone = resample(pcm, rate, 8000)
    write_wav(OUT / "question-8k-resampled.wav", phone, 8000)
    # Telephone rate and the mu-law codec, as on a phone line.
    write_wav(OUT / "question-8k-mulaw.wav", mulaw_roundtrip(phone), 8000)
    # A 5,000 Hz tone, too high for an 8,000-samples-a-second signal.
    beep = tone(5000, rate, 2.0)
    write_wav(OUT / "tone-5000hz.wav", beep, rate)
    write_wav(OUT / "tone-8k-naive.wav", naive_downsample(beep, 2), 8000)
    write_wav(OUT / "tone-8k-resampled.wav", resample(beep, rate, 8000), 8000)
    for f in sorted(OUT.glob("*.wav")):
        print(f"wrote {f}")


def inspect() -> None:
    print(f"{'file':<28}{'rate':>7}{'seconds':>9}{'loudness':>10}"
          f"{'peak Hz':>9}{'>3.4k':>8}")
    for f in [Path(QUESTION), *sorted(OUT.glob("*.wav"))]:
        pcm, rate = read_wav(str(f))
        high = energy_above(pcm, rate, 3400)
        print(f"{f.name:<28}{rate:>7}{len(pcm) / rate:>9.2f}"
              f"{rms(pcm):>10.0f}{dominant_frequency(pcm, rate):>9.0f}"
              f"{100 * high:>7.1f}%")


if __name__ == "__main__":
    {"make": make, "inspect": inspect}[sys.argv[1]]()
