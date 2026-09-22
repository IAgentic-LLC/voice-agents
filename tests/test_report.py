"""Pin the numbers Chapter 1 prints, from the recorded runs."""

from report import summarize
from voicelab import runlog


def runlog_trials(run):
    return runlog.read(f"runs/{run}/trials.jsonl")


def test_realtime_run():
    s = summarize("runs/ch01-realtime")
    assert (s["joined"], s["answered"]) == (10, 10)
    assert round(s["ttfa_median"], 3) == 0.727


def test_unpaced_caller_added_error():
    s = summarize("runs/ch01-unpaced-caller")
    assert round(s["ttfa_median"], 3) == 1.664
    # The question "ended" about a second early: the clock started while
    # the last second of audio was still waiting to be sent.
    trials = runlog_trials("ch01-unpaced-caller")
    assert max(t["question_s"] for t in trials) < 5.8


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


def test_half_answer_heard_only_with_the_fast_voice():
    from timeline import events_for
    from voicelab import runlog

    def heard_before_second_model_call(run):
        calls = runlog.read(f"runs/{run}/trials.jsonl")
        stages = runlog.read(f"runs/{run}/stages.jsonl")
        heard = []
        for call in calls:
            if not call["ok"]:
                continue
            events = events_for(call, stages)
            second = [e for e in events if e[1] == "model"][1][0]
            audio = [
                float(e[2].split(", ")[1].split(" s")[0])
                for e in events if e[1] == "speech" and e[0] < second
            ]
            heard.append(sum(audio))
        return heard

    assert max(heard_before_second_model_call("ch01-cascaded-split")) == 0
    assert min(heard_before_second_model_call("ch01-tts-daily-limit")) >= 1.5
