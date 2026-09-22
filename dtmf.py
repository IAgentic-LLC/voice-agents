"""Chapter 13: the tones a telephone keypad makes, and how to read them.

    uv run dtmf.py make 4721 audio/ch13/keys-4721.wav
    uv run dtmf.py decode audio/ch13/keys-4721.wav
    uv run dtmf.py heard runs/ch13-keys runs/ch13-keys-long

A keypress on a telephone is two tones at once, one from a row and one
from a column of the keypad. That is all it is: no packet, no message,
just sound on the same line as the voice. ITU-T Recommendation Q.23
fixes the eight frequencies.

Reading them back is not speech recognition and does not need a model.
Each pair is two pure tones, so measuring the energy at eight known
frequencies is enough, which is what the Goertzel algorithm does
cheaply. Needs no key.

`heard` reads a recorded run and reports what the speech side made of
the same tones: how often the voice detector called them speech, and
what the transcriber wrote down.
"""

import sys
from pathlib import Path

import numpy as np

from voicelab.audio import read_wav, write_wav

LOW = (697, 770, 852, 941)
HIGH = (1209, 1336, 1477, 1633)
KEYS = (
    ("1", "2", "3", "A"),
    ("4", "5", "6", "B"),
    ("7", "8", "9", "C"),
    ("*", "0", "#", "D"),
)
TONE_S = 0.15    # how long a key is held
GAP_S = 0.10     # and the quiet between keys
RATE = 8000      # the telephone rate, as in Chapter 2
LEVEL = 8000     # well below full scale, so the pair does not clip


def pair_for(key: str) -> tuple[int, int]:
    for row, keys in enumerate(KEYS):
        if key in keys:
            return LOW[row], HIGH[keys.index(key)]
    raise SystemExit(f"{key!r} is not on a telephone keypad")


def make(digits: str, path: str) -> None:
    parts = []
    for key in digits:
        low, high = pair_for(key)
        t = np.arange(int(TONE_S * RATE)) / RATE
        tone = (np.sin(2 * np.pi * low * t)
                + np.sin(2 * np.pi * high * t)) * (LEVEL / 2)
        parts.append(tone.astype(np.int16))
        parts.append(np.zeros(int(GAP_S * RATE), dtype=np.int16))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    write_wav(path, np.concatenate(parts), RATE)
    print(f"wrote {path}  ({digits}, {len(digits)} keys, "
          f"{sum(len(p) for p in parts) / RATE:.2f} s)")


def goertzel(samples: np.ndarray, rate: int, freq: float) -> float:
    """How much of one exact frequency is in this block of samples."""
    n = len(samples)
    k = int(0.5 + n * freq / rate)
    w = 2 * np.pi * k / n
    coeff = 2 * np.cos(w)
    s_prev = s_prev2 = 0.0
    for sample in samples.astype(np.float64):
        s = sample + coeff * s_prev - s_prev2
        s_prev2, s_prev = s_prev, s
    return s_prev2**2 + s_prev**2 - coeff * s_prev * s_prev2


def decode(path: str) -> list[str]:
    """Which keys were pressed, from the sound alone."""
    pcm, rate = read_wav(path)
    step = int(0.02 * rate)  # 20 ms, shorter than any key press
    found, last = [], None
    for i in range(0, len(pcm) - step, step):
        block = pcm[i : i + step]
        if np.sqrt(np.mean(block.astype(np.float64) ** 2)) < 300:
            last = None  # silence between keys
            continue
        low = max(LOW, key=lambda f: goertzel(block, rate, f))
        high = max(HIGH, key=lambda f: goertzel(block, rate, f))
        key = KEYS[LOW.index(low)][HIGH.index(high)]
        if key != last:
            found.append(key)
            last = key
    return found


def heard(runs: list[str]) -> None:
    """What the speech path made of the keys, per recorded run."""
    from voicelab import runlog

    print(f"{'run':<20}{'calls':>6}{'detector heard speech':>24}"
          f"{'transcripts':>13}")
    for run in runs:
        calls = runlog.read(f"{run}/trials.jsonl")
        trace = [t for t in runlog.read(f"{run}/stages.jsonl")
                 if t.get("stage") == "trace"]
        speaking = len({t["room"] for t in trace
                        if t["event"] == "user speaking"})
        said = [t["text"] for t in trace if t["event"] == "user said"]
        print(f"{run.split('/')[-1]:<20}{len(calls):>6}"
              f"{speaking:>16} of {len(calls)}{len(said):>13}")
        for text in said:
            print(f"    transcript: {text!r}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["heard"]:
        heard(sys.argv[2:])
    elif sys.argv[1:2] == ["make"]:
        make(sys.argv[2], sys.argv[3])
    elif sys.argv[1:2] == ["decode"]:
        keys = decode(sys.argv[2])
        print(f"heard {len(keys)} key(s): {''.join(keys)}")
    else:
        raise SystemExit(__doc__.splitlines()[2].strip())
