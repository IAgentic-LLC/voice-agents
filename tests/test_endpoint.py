"""Pin the Chapter 6 endpointing results."""

import statistics
from pathlib import Path

import numpy as np

import pauses
from endpoint import call_turns, pause_of
from pauses import longest_inner_pause
from voicelab import runlog
from voicelab.audio import read_wav
from voicelab.question import QUESTION

STREAMING = ("ch06-a", "ch06-b", "ch06-c", "ch06-d")


def calls_of(run):
    calls = [c for c in runlog.read(f"runs/{run}/trials.jsonl")
             if "speech_end_wall" in c]
    traces = [s for s in runlog.read(f"runs/{run}/stages.jsonl")
              if s["stage"] == "trace"]
    return [(c, *call_turns(c, traces)) for c in calls]


def whole_by_pause(run):
    """{pause: how many of that pause's calls kept the question whole}."""
    out = {}
    for call, turns, _ in calls_of(run):
        pause = pause_of(call)
        out[pause] = out.get(pause, 0) + (turns == 1)
    return out


def handoff_median(run):
    waits = [w for _, turns, w in calls_of(run) if turns == 1 and w]
    return statistics.median(waits)


def test_every_arm_ran_ten_calls():
    for run in STREAMING + ("ch06-e", "ch06-f"):
        assert len(calls_of(run)) == 10


def test_streaming_settings_changed_nothing():
    for run in STREAMING:
        assert set(whole_by_pause(run).values()) == {2}  # never split
    medians = [handoff_median(run) for run in STREAMING]
    assert 1.5 < min(medians) and max(medians) < 1.62
    assert max(medians) - min(medians) < 0.07


def test_batch_splits_where_the_threshold_is_crossed():
    # The detector's estimate of the end of speech lands about 0.19 s
    # late, so it measures a gap that much shorter than the recording's.
    assert whole_by_pause("ch06-e") == {0.3: 2, 0.6: 2, 0.9: 0, 1.2: 0,
                                        1.8: 0}
    assert whole_by_pause("ch06-f") == {0.3: 2, 0.6: 2, 0.9: 2, 1.2: 2,
                                        1.8: 0}


def test_patience_costs_the_calls_that_did_not_need_it():
    cost = handoff_median("ch06-f") - handoff_median("ch06-e")
    assert round(cost, 3) == 0.781


def test_the_pause_in_the_recording():
    pcm, rate = read_wav(QUESTION)
    start, end = longest_inner_pause(pcm, rate)
    assert (round(start / rate, 2), round(end / rate, 2)) == (3.10, 4.00)


def test_pause_variants_change_only_the_pause():
    """Each variant is the original with a different gap in the middle."""
    if not Path("audio/ch06/question-pause-0.3.wav").exists():
        pauses.main()  # the recordings are generated, not committed
    original, rate = read_wav(QUESTION)
    start, end = longest_inner_pause(original, rate)
    for seconds in (0.3, 0.6, 1.2, 1.8):
        pcm, _ = read_wav(f"audio/ch06/question-pause-{seconds:.1f}.wav")
        assert np.array_equal(pcm[:start], original[:start])
        assert np.array_equal(pcm[-(len(original) - end):],
                              original[end:])
        assert abs(len(pcm) - len(original)
                   - (seconds - (end - start) / rate) * rate) < rate / 100
