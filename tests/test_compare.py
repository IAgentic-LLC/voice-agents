"""Pin the Chapter 8 comparison of cascaded and realtime."""

import statistics

from compare import answers, priced, usage_of
from report import summarize
from voicelab.policy import TASKS, task_of
from voicelab.stats import bootstrap_difference_interval


def test_both_agents_answered_every_task_correctly():
    for run in ("runs/ch08-cascaded", "runs/ch08-realtime"):
        scored = answers(run)
        assert len(scored) == 10
        assert all(ok for _, _, ok in scored)
        # Every task was put to each agent twice.
        names = sorted(name for name, _, _ in scored)
        assert names == sorted(t.name for t in TASKS for _ in (1, 2))


def test_realtime_answers_sooner_and_more_evenly():
    cascaded = summarize("runs/ch08-cascaded")["ttfa"]
    realtime = summarize("runs/ch08-realtime")["ttfa"]
    assert round(statistics.median(cascaded), 3) == 6.071
    assert round(statistics.median(realtime), 3) == 1.523
    low, high = bootstrap_difference_interval(cascaded, realtime)
    assert high < 0  # the whole interval is below zero
    assert (round(low, 3), round(high, 3)) == (-6.540, -3.953)
    # And its calls sit closer together than the cascaded agent's.
    assert max(realtime) - min(realtime) < max(cascaded) - min(cascaded)


def test_the_realtime_call_can_be_priced_and_the_cascaded_one_cannot():
    for models in usage_of("runs/ch08-realtime"):
        cost, missing = priced(models)
        assert cost > 0 and not missing
    for models in usage_of("runs/ch08-cascaded"):
        cost, missing = priced(models)
        assert cost > 0
        assert missing == ["gemini-2.5-flash-preview-tts"]


def test_the_speech_stage_reports_seconds_but_no_tokens():
    """The reason the bill cannot be reconstructed."""
    for models in usage_of("runs/ch08-cascaded"):
        tts = [m for m in models if m["type"] == "tts_usage"][0]
        assert tts["audio_duration"] > 0
        assert tts["characters_count"] > 0
        assert tts["input_tokens"] == 0 and tts["output_tokens"] == 0


def test_both_stacks_report_what_they_said():
    """The realtime model transcribes its own speech."""
    for run in ("runs/ch08-cascaded", "runs/ch08-realtime"):
        assert all(answer for _, answer, _ in answers(run))


def test_a_wrong_answer_would_be_caught():
    """The scoring is weak, but it is not vacuous."""
    refund = task_of("audio/refund_question.wav")
    assert refund.passed("it reaches your bank in 5 to 10 business days")
    assert not refund.passed("refunds are issued within one business day")
