"""Pin the numbers Chapter 1 prints, from the recorded runs."""

from report import summarize


def test_realtime_run():
    s = summarize("runs/ch01-realtime")
    assert (s["joined"], s["answered"]) == (10, 10)
    assert round(s["ttfa_median"], 3) == 0.727


def test_unpaced_caller_added_error():
    s = summarize("runs/ch01-unpaced-caller")
    assert round(s["ttfa_median"], 3) == 1.610


def test_split_run_answered_each_half():
    s = summarize("runs/ch01-cascaded-split")
    assert s["answered"] == 9 and s["model_calls"] == 18
    assert len(s["transcripts"]) == 2


def test_whole_run_heard_one_question():
    s = summarize("runs/ch01-cascaded-whole")
    assert s["answered"] == 10 and s["model_calls"] == 10
    assert len(s["transcripts"]) == 1
    assert round(s["ttfa_median"], 3) == 5.844
    assert round(s["speech_first_byte_s"], 3) == 2.897


def test_cancelled_speech_is_not_timed():
    s = summarize("runs/ch01-tts-daily-limit")
    assert round(s["speech_first_byte_s"], 3) == 0.853
