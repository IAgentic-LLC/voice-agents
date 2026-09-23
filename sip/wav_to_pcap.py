"""Chapter 14: turn a recording into RTP packets a softphone can play.

    uv run sip/wav_to_pcap.py audio/ch09/plain.wav sip/plain.pcap

SIPp plays media by replaying a capture file, so to send this book's
own question down a real phone line the question has to become RTP
packets first. That means three things the telephone does anyway:
resample to 8,000 samples a second, encode to G.711 mu-law, and cut
the result into 20 millisecond packets.

Doing it here rather than trusting a sample file means the sentence
going down the phone is the same sentence every earlier chapter used,
so the numbers can be compared.
"""

import struct
import sys

import numpy as np

sys.path.insert(0, ".")
from voicelab.audio import read_wav, resample  # noqa: E402

RATE = 8000
PTIME_MS = 20
SAMPLES = RATE * PTIME_MS // 1000   # 160 bytes of mu-law per packet
PAYLOAD_TYPE = 0                    # PCMU, as named in the SDP
BIAS = 0x84
CLIP = 8159
# The top of each of the eight mu-law segments, from the standard.
SEG_END = np.array([0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF,
                    0x1FFF], dtype=np.int32)


def lin2ulaw(pcm: np.ndarray) -> bytes:
    """G.711 mu-law, the segmented encoder the standard defines.

    Chapter 2's `mulaw_roundtrip` uses the continuous formula, which
    is fine for measuring what the curve costs a voice. A packet on a
    real line needs the actual bytes, and those come from this: shift
    to 14 bits, add the bias, find which of eight segments the sample
    lands in, and keep four bits of where it sits inside that segment.
    """
    x = pcm.astype(np.int32) >> 2            # 16 bits down to 14
    mask = np.where(x < 0, 0x7F, 0xFF).astype(np.int32)
    x = np.minimum(np.abs(x), CLIP) + (BIAS >> 2)
    seg = np.searchsorted(SEG_END, x, side="left").astype(np.int32)
    uval = (seg << 4) | ((x >> (seg + 1)) & 0x0F)
    uval = np.where(seg >= 8, 0x7F, uval) ^ mask
    return bytes(uval.astype(np.uint8))


def ulaw2lin(data: bytes) -> np.ndarray:
    """Back again, so a test can ask what the line cost the voice."""
    u = (~np.frombuffer(data, dtype=np.uint8).astype(np.int32)) & 0xFF
    seg = (u >> 4) & 0x07
    mantissa = u & 0x0F
    value = ((mantissa << 1) + 33) << seg
    value = (value - BIAS) << 2
    return np.where(u & 0x80, -value, value).astype(np.int16)


def packet(payload: bytes, seq: int, stamp: int, ssrc: int) -> bytes:
    """One RTP packet inside UDP inside IP inside Ethernet.

    SIPp rewrites the addresses and ports when it replays this, so the
    ones here only have to be well formed.
    """
    rtp = struct.pack("!BBHII", 0x80, PAYLOAD_TYPE, seq & 0xFFFF,
                      stamp & 0xFFFFFFFF, ssrc) + payload
    udp = struct.pack("!HHHH", 40000, 40000, 8 + len(rtp), 0) + rtp
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(udp), 0, 0, 64,
                     17, 0, bytes((10, 0, 0, 1)), bytes((10, 0, 0, 2)))
    return b"\xaa" * 6 + b"\xbb" * 6 + b"\x08\x00" + ip + udp


def write_pcap(path: str, frames: list[bytes]) -> None:
    with open(path, "wb") as out:
        out.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0,
                              65535, 1))
        usec = 0
        for frame in frames:
            out.write(struct.pack("<IIII", usec // 1_000_000,
                                  usec % 1_000_000, len(frame),
                                  len(frame)))
            out.write(frame)
            usec += PTIME_MS * 1000


def convert(src: str, dst: str) -> None:
    pcm, rate = read_wav(src)
    if rate != RATE:
        pcm = resample(pcm, rate, RATE)
    ulaw = lin2ulaw(pcm)
    frames, seq, stamp = [], 0, 0
    for i in range(0, len(ulaw) - SAMPLES + 1, SAMPLES):
        frames.append(packet(ulaw[i:i + SAMPLES], seq, stamp, 0x1234ABCD))
        seq, stamp = seq + 1, stamp + SAMPLES
    write_pcap(dst, frames)
    print(f"wrote {dst}  ({len(frames)} packets, "
          f"{len(frames) * PTIME_MS / 1000:.2f} s, G.711 mu-law)")


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
