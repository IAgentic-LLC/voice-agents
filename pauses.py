"""Chapter 6: the same question with a longer or shorter pause in the middle.

    uv run pauses.py            # writes audio/ch06/question-pause-*.wav

The recording pauses for 0.90 s between its two sentences. This finds that
pause and replaces it with quiet room tone taken from the pause itself, so
only the pause length changes. Needs no key.
"""

from pathlib import Path

import numpy as np

from voicelab.audio import read_wav, write_wav
from voicelab.question import AUDIBLE_RMS, QUESTION

PAUSES = [0.3, 0.6, 0.9, 1.2, 1.8]
OUT = Path("audio/ch06")


def longest_inner_pause(pcm: np.ndarray, rate: int) -> tuple[int, int]:
    """Start and end sample of the longest quiet stretch between words."""
    step = rate // 100
    loud = [
        np.sqrt(np.mean(pcm[i : i + step].astype(np.float64) ** 2))
        > AUDIBLE_RMS
        for i in range(0, len(pcm), step)
    ]
    first, last = loud.index(True), len(loud) - 1 - loud[::-1].index(True)
    best, start = (0, 0), None
    for n in range(first, last + 1):
        if not loud[n] and start is None:
            start = n
        if loud[n] and start is not None:
            if n - start > best[1] - best[0]:
                best = (start, n)
            start = None
    return best[0] * step, best[1] * step


def main() -> None:
    pcm, rate = read_wav(QUESTION)
    a, b = longest_inner_pause(pcm, rate)
    print(f"pause found: {a / rate:.2f} s to {b / rate:.2f} s "
          f"({(b - a) / rate:.2f} s)")
    tone = pcm[a:b]
    OUT.mkdir(parents=True, exist_ok=True)
    for seconds in PAUSES:
        n = int(seconds * rate)
        quiet = np.resize(tone, n)  # repeat or trim the room tone
        new = np.concatenate([pcm[:a], quiet, pcm[b:]])
        path = OUT / f"question-pause-{seconds:.1f}.wav"
        write_wav(path, new, rate)
        print(f"wrote {path.as_posix()}  ({len(new) / rate:.2f} s)")


if __name__ == "__main__":
    main()
