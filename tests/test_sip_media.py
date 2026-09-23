"""Chapter 14: the G.711 encoder that puts this book's audio on a line."""

import struct
import sys

import numpy as np

sys.path.insert(0, "sip")
import wav_to_pcap as w  # noqa: E402

from voicelab.audio import read_wav, resample  # noqa: E402

# Taken from Python's own audioop.lin2ulaw, which implements the
# standard, on 2026-09-23: silence, then one sample in each of several
# segments, positive and negative. audioop is removed in Python 3.13,
# which is why these are written down rather than computed. My first
# attempt at this encoder disagreed with the reference on half the
# bytes of a real recording, so it is worth pinning.
GOLDEN = {
    0: 0xFF,
    1: 0xFF,
    100: 0xF2,
    1000: 0xCE,
    5000: 0xAB,
    32000: 0x80,
    -100: 0x72,
    -1000: 0x4E,
    -32000: 0x00,
}


def test_the_encoder_matches_the_standard_byte_for_byte():
    values = np.array(list(GOLDEN), dtype=np.int16)
    got = w.lin2ulaw(values)
    # zip stops at the shorter one, so a truncated result would
    # skip the loop entirely and pass. That is the exact bug this
    # test exists to catch.
    assert len(got) == len(values)
    for value, byte in zip(values, got):
        assert byte == GOLDEN[int(value)], f"{value} gave {byte:#04x}"


def test_loud_and_quiet_do_not_collapse_to_the_same_byte():
    """mu-law keeps quiet sounds apart, which is the whole point."""
    quiet = w.lin2ulaw(np.array([10, 40, 80], dtype=np.int16))
    assert len(set(quiet)) == 3


def test_a_packet_is_a_real_rtp_packet():
    payload = bytes(range(160))
    frame = w.packet(payload, seq=7, stamp=1600, ssrc=0x1234ABCD)
    assert len(frame) == 14 + 20 + 8 + 12 + 160
    assert frame[12:14] == b"\x08\x00"          # Ethernet says IPv4
    assert frame[23] == 17                      # IPv4 says UDP
    rtp = frame[42:]
    version_and_flags, payload_type, seq = struct.unpack("!BBH", rtp[:4])
    assert version_and_flags >> 6 == 2          # RTP version 2
    assert payload_type == 0                    # PCMU, as the SDP says
    assert seq == 7
    assert rtp[12:] == payload


def test_the_question_becomes_the_right_number_of_packets(tmp_path):
    """3.6 seconds of speech is 180 packets of 20 milliseconds."""
    out = str(tmp_path / "q.pcap")
    w.convert("audio/ch09/plain.wav", out)
    data = open(out, "rb").read()
    magic, major = struct.unpack("<IH", data[:6])
    assert magic == 0xA1B2C3D4 and major == 2
    assert struct.unpack("<I", data[20:24])[0] == 1   # Ethernet
    count, i = 0, 24
    while i < len(data):
        length = struct.unpack("<I", data[i + 8:i + 12])[0]
        count += 1
        i += 16 + length
    assert count == 180


def test_the_line_keeps_the_voice_recognisable(tmp_path):
    """Chapter 2 measured this as a loss. It is a small one."""
    pcm, rate = read_wav("audio/ch09/plain.wav")
    eight = resample(pcm, rate, 8000)
    back = w.ulaw2lin(w.lin2ulaw(eight))
    n = min(len(back), len(eight))
    keep = np.corrcoef(back[:n].astype(float),
                       eight[:n].astype(float))[0, 1]
    assert keep > 0.99, f"correlation fell to {keep:.4f}"
