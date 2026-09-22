"""Audio as numbers: read, write, resample, compress and inspect.

Everything here works on mono 16-bit PCM held in a NumPy int16 array, the
format the rest of the book uses.
"""

import wave

import numpy as np
from livekit import rtc


def read_wav(path: str) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        return pcm, w.getframerate()


def write_wav(path: str, pcm: np.ndarray, rate: int) -> None:
    """Write mono 16-bit PCM. The header records `rate`, and a player
    believes the header, whatever rate the samples were really made at."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.astype(np.int16).tobytes())


def tone(freq: float, rate: int, seconds: float, level: int = 8000):
    t = np.arange(int(rate * seconds)) / rate
    return (level * np.sin(2 * np.pi * freq * t)).astype(np.int16)


def naive_downsample(pcm: np.ndarray, factor: int) -> np.ndarray:
    """Keep every factor-th sample and throw the rest away. No filter."""
    return pcm[::factor].copy()


def resample(pcm: np.ndarray, rate_in: int, rate_out: int) -> np.ndarray:
    """Resample with LiveKit's resampler (the SoX library underneath),
    which filters out what the new rate cannot hold before it drops
    samples."""
    resampler = rtc.AudioResampler(
        rate_in, rate_out, quality=rtc.AudioResamplerQuality.HIGH
    )
    step = rate_in // 100  # feed it 10 ms frames, as a live call would
    frames = []
    for i in range(0, len(pcm), step):
        chunk = pcm[i : i + step]
        chunk = np.pad(chunk, (0, step - len(chunk)))
        frame = rtc.AudioFrame(chunk.tobytes(), rate_in, 1, step)
        frames += resampler.push(frame)
    frames += resampler.flush()
    out = np.concatenate(
        [np.frombuffer(f.data, dtype=np.int16) for f in frames]
    )
    return out[: round(len(pcm) * rate_out / rate_in)]


MU = 255  # the mu-law constant used by G.711 in North America and Japan


def mulaw_roundtrip(pcm: np.ndarray) -> np.ndarray:
    """Squeeze each sample into 8 bits with the mu-law curve, then expand it
    back. This is the continuous mu-law formula; G.711 itself uses a close
    table-based approximation of it."""
    x = pcm.astype(np.float64) / 32768.0
    y = np.sign(x) * np.log1p(MU * np.abs(x)) / np.log1p(MU)
    code = np.round(y * 127)  # 8 bits: -127 to 127
    y = code / 127
    x = np.sign(y) * ((1 + MU) ** np.abs(y) - 1) / MU
    return np.clip(x * 32768.0, -32768, 32767).astype(np.int16)


def dominant_frequency(pcm: np.ndarray, rate: int) -> float:
    """The loudest frequency, ignoring anything below 20 Hz: a recording
    can carry a small constant offset that would otherwise win."""
    spectrum = np.abs(np.fft.rfft(pcm.astype(np.float64)))
    freqs = np.fft.rfftfreq(len(pcm), 1 / rate)
    spectrum[freqs < 20] = 0
    return float(freqs[int(np.argmax(spectrum))])


def energy_above(pcm: np.ndarray, rate: int, cutoff: float) -> float:
    """Share of the signal's energy at frequencies above `cutoff`."""
    power = np.abs(np.fft.rfft(pcm.astype(np.float64))) ** 2
    freqs = np.fft.rfftfreq(len(pcm), 1 / rate)
    return float(power[freqs > cutoff].sum() / power.sum())


def rms(pcm: np.ndarray) -> float:
    return float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2)))
