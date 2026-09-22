"""Pin the Chapter 5 comparison of batch and streaming transcription."""

import statistics

from report import summarize
from voicelab import runlog
from voicelab.stats import bootstrap_difference_interval
from waterfall import call_events, stage_lengths


def stage_median(run, stage):
    calls = runlog.read(f"runs/{run}/trials.jsonl")
    traces = [s for s in runlog.read(f"runs/{run}/stages.jsonl")
              if s["stage"] == "trace"]
    return statistics.median(
        stage_lengths(call_events(c, traces))[stage] for c in calls
    )


def test_streaming_shrinks_transcription():
    assert round(stage_median("ch05-batch", "transcription"), 3) == 1.695
    assert round(stage_median("ch05-stream", "transcription"), 3) == 0.167


def test_streaming_is_faster_overall():
    batch = summarize("runs/ch05-batch")
    stream = summarize("runs/ch05-stream")
    assert round(stream["ttfa_median"] - batch["ttfa_median"], 3) == -1.649
    low, high = bootstrap_difference_interval(batch["ttfa"], stream["ttfa"])
    assert (round(low, 3), round(high, 3)) == (-2.555, -0.180)
    assert high < 0  # the whole interval is below zero


def test_silence_wait_is_unchanged():
    for run in ("ch05-batch", "ch05-stream"):
        assert 1.3 < stage_median(run, "waiting out the silence") < 1.4
