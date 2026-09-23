"""Chapter 13: the tones a telephone keypad makes, and how to read them.

    uv run dtmf.py make 4721 audio/ch13/keys-4721.wav
    uv run dtmf.py decode audio/ch13/keys-4721.wav
    uv run dtmf.py phone audio/ch13/keys-4721.wav audio/ch13/keys-phone.wav
    uv run dtmf.py sweep audio/ch13/keys-long.wav audio/ch09/plain.wav
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

from voicelab.audio import mulaw_roundtrip, read_wav, write_wav

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

# These tones are idealised. A real keypad sends the column tone
# about 2 dB above the row tone, and real receivers enforce limits on
# that difference, which is called twist. Both tones here have the
# same amplitude, so nothing in this file tests twist at all.


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


DOMINANCE = 8.0  # how far ahead the winning tone has to be


def decode(path: str, dominance: float = 0.0) -> list[str]:
    """Which keys were pressed, from the sound alone.

    With dominance at 0 this takes the loudest row and the loudest
    column in every block and always names a key, which is what makes
    it read digits out of ordinary speech. A real detector demands
    that the winner actually dominate its rivals; pass a dominance
    ratio to require that here.
    """
    pcm, rate = read_wav(path)
    step = int(0.02 * rate)  # 20 ms, shorter than any key press
    found, last = [], None
    for i in range(0, len(pcm) - step, step):
        block = pcm[i : i + step]
        if np.sqrt(np.mean(block.astype(np.float64) ** 2)) < 300:
            last = None  # silence between keys
            continue
        lows = sorted(((goertzel(block, rate, f), f) for f in LOW),
                      reverse=True)
        highs = sorted(((goertzel(block, rate, f), f) for f in HIGH),
                       reverse=True)
        if dominance and not (lows[0][0] > dominance * lows[1][0]
                              and highs[0][0] > dominance * highs[1][0]):
            last = None  # a voice, or noise: no pair stands out
            continue
        key = KEYS[LOW.index(lows[0][1])][HIGH.index(highs[0][1])]
        if key != last:
            found.append(key)
            last = key
    return found


def phone(src: str, dst: str) -> None:
    """Put a file through what a telephone line does to it.

    G.711 mu-law is the codec on almost every call, and Chapter 2
    already measured what it costs a voice. The question here is
    whether it costs the tones anything.
    """
    pcm, rate = read_wav(src)
    write_wav(dst, mulaw_roundtrip(pcm), rate)
    print(f"wrote {dst}  (G.711 mu-law roundtrip)")


def sweep(keys_path: str, *speech_paths: str) -> None:
    """How wide is the window where the guard works?

    Too low and a voice reads as keypresses. Too high and blocks in
    the middle of a real key fail the test, which resets the decoder
    and makes it report the same key twice. The blocks that fail are
    not the quiet ones at the edges of a keypress: a 20 ms block at
    8 kHz resolves frequency to 50 Hz steps, and 770 Hz lands 20 Hz
    off its nearest step, so the four keys on that row never lead by
    much and are the first to break.

    Pass more than one speech file. The window looks comfortable
    against one recording and shuts against the next.
    """
    expected = "".join(decode(keys_path))
    names = [p.split("/")[-1].removesuffix(".wav") for p in speech_paths]
    print(f"{'dominance':>9}{'keys read':>16}"
          + "".join(f"{n:>17}" for n in names))
    for t in (0, 2, 4, 6, 8, 9, 10, 11, 12, 20, 31, 40):
        got = "".join(decode(keys_path, t))
        mark = "correct" if got == expected else got[:14]
        counts = "".join(f"{len(decode(p, t)):>17}" for p in speech_paths)
        print(f"{t:>9}{mark:>16}{counts}")


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
        # "final transcript" is what the speech model produced.
        # "user said" is what survived to the chat context. Count the
        # first: a model can transcribe without the turn ever ending.
        said = [t["text"] for t in trace
                if t["event"] in ("final transcript", "user said")]
        print(f"{run.split('/')[-1]:<20}{len(calls):>6}"
              f"{speaking:>16} of {len(calls)}{len(said):>13}")
        for text in said:
            print(f"    transcript: {text!r}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["heard"]:
        heard(sys.argv[2:])
    elif sys.argv[1:2] == ["make"]:
        make(sys.argv[2], sys.argv[3])
    elif sys.argv[1:2] == ["sweep"]:
        sweep(sys.argv[2], *sys.argv[3:])
    elif sys.argv[1:2] == ["phone"]:
        phone(sys.argv[2], sys.argv[3])
    elif sys.argv[1:2] == ["decode"]:
        strict = "--strict" in sys.argv
        keys = decode(sys.argv[2], DOMINANCE if strict else 0.0)
        how = " (strict)" if strict else ""
        print(f"heard {len(keys)} key(s){how}: {''.join(keys)}".rstrip())
    else:
        raise SystemExit(__doc__.splitlines()[2].strip())
