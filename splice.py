"""Chapter 9: join two recordings with a pause, to split one turn in two.

    uv run splice.py audio/ch09/split_change.wav 2.0 \
      audio/ch09/plain.wav audio/ch09/actually_friday.wav
    uv run splice.py audio/ch09/asked_twice.wav 2.0 \
      audio/ch09/plain.wav audio/ch09/plain.wav

A speech model will not leave a two-second gap in the middle of a
sentence, so the gap is inserted here. The quiet between the recordings
is room tone taken from the first one, not digital silence, for the
reason Chapter 6 gives: a detector trained on real rooms treats the two
differently. Needs no key.
"""

import sys

import numpy as np

from voicelab.audio import read_wav, write_wav
from voicelab.question import AUDIBLE_RMS


def loud_span(pcm: np.ndarray, rate: int) -> tuple[int, int]:
    """First and last sample of the recording that is loud enough to hear."""
    step = rate // 100
    loud = [
        np.sqrt(np.mean(pcm[i : i + step].astype(np.float64) ** 2))
        > AUDIBLE_RMS
        for i in range(0, len(pcm), step)
    ]
    return loud.index(True) * step, (len(loud) - loud[::-1].index(True)) * step


def splice(out: str, gap_s: float, parts: list[str]) -> None:
    pieces, rate = [], 0
    tone = None
    last = len(parts) - 1
    for n, path in enumerate(parts):
        pcm, rate = read_wav(path)
        start, end = loud_span(pcm, rate)
        if tone is None:  # the first recording's own quiet, for the gaps
            tone = pcm[end:] if len(pcm) - end > rate // 10 else pcm[:start]
        if n:
            pieces.append(np.resize(tone, int(gap_s * rate)))
        # Keep the first recording's lead-in and the last one's tail, so
        # the join has the same quiet edges a single recording would.
        head = 0 if n == 0 else start
        tail = len(pcm) if n == last else end
        pieces.append(pcm[head:tail])
    joined = np.concatenate(pieces)
    write_wav(out, joined, rate)
    print(f"wrote {out}  ({len(joined) / rate:.2f} s, "
          f"{len(parts) - 1} gap(s) of {gap_s:.2f} s)")


if __name__ == "__main__":
    if len(sys.argv) < 5:
        raise SystemExit(__doc__.splitlines()[2].strip())
    splice(sys.argv[1], float(sys.argv[2]), sys.argv[3:])
