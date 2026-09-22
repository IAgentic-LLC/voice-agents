"""Pin what Chapter 2 says about sample rates, aliasing and the codec."""

import numpy as np

from transcribe_variants import report  # noqa: F401  (import check)
from voicelab import runlog
from voicelab.audio import (
    dominant_frequency,
    mulaw_roundtrip,
    naive_downsample,
    read_wav,
    resample,
    rms,
    tone,
)
from voicelab.wer import word_error_rate

SAID = ("Hi, I was charged twice for my last invoice. "
        "Can you tell me how a refund works?")


def test_naive_downsampling_invents_a_3000_hz_tone():
    beep = tone(5000, 16000, 2.0)
    folded = naive_downsample(beep, 2)
    assert dominant_frequency(folded, 8000) == 3000
    assert rms(folded) > 5000  # as loud as the original


def test_resampler_removes_what_8000_cannot_hold():
    beep = tone(5000, 16000, 2.0)
    assert rms(resample(beep, 16000, 8000)) < 100


def test_the_label_changes_pitch_by_the_ratio():
    pcm, rate = read_wav("audio/refund_question.wav")
    assert round(dominant_frequency(pcm, rate)) == 87
    assert round(dominant_frequency(pcm, 24000)) == 130
    assert round(dominant_frequency(pcm, 8000)) == 43


def test_mulaw_keeps_the_shape():
    pcm, _ = read_wav("audio/refund_question.wav")
    back = mulaw_roundtrip(pcm)
    assert abs(rms(back) - rms(pcm)) / rms(pcm) < 0.05


def test_word_error_rate():
    assert word_error_rate(SAID, SAID.upper()) == 0
    assert round(word_error_rate(SAID, SAID + " please"), 4) == 0.0588


def test_recorded_transcripts():
    rows = runlog.read("runs/ch02-transcripts/transcripts.jsonl")
    assert len(rows) == 30
    slow = [r for r in rows if r["version"] == "question-labelled-8k.wav"]
    assert all(r["wer"] > 0 for r in slow)
    assert all(r["wer"] == 0 for r in rows if r not in slow)
