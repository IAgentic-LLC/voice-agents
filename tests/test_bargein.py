"""Pin the Chapter 7 barge-in results."""

import statistics

from bargein import answer_s, read, resumed
from voicelab import runlog
from voicelab.stats import bootstrap_difference_interval


def stops(run):
    return [c["stop_s"] for c in read(f"runs/{run}")]


def never_stopped(run):
    """The agent talked until the recording ran out."""
    whole = answer_s(f"runs/{run}")
    return all(c["stop_s"] > whole - c["interrupt_after_s"] - 2
               for c in read(f"runs/{run}"))


def test_the_setting_sets_the_floor():
    for run, setting in (("ch07-b", 0.2), ("ch07-a", 0.5), ("ch07-c", 1.0)):
        stop = statistics.median(stops(run))
        assert setting < stop < setting + 0.3  # the setting, plus the trip


def test_arm_medians():
    assert round(statistics.median(stops("ch07-a")), 3) == 0.721
    assert round(statistics.median(stops("ch07-b")), 3) == 0.421
    assert round(statistics.median(stops("ch07-c")), 3) == 1.154


def test_an_agent_with_interruptions_off_never_stops():
    assert never_stopped("ch07-d")
    assert statistics.median(
        c["heard_after_s"] for c in read("runs/ch07-d")
    ) > 13


def test_a_backchannel_stops_it_as_fast_as_a_real_interruption():
    """Arm E is arm B with "Mhm." instead of an objection."""
    low, high = bootstrap_difference_interval(stops("ch07-b"),
                                              stops("ch07-e"))
    assert low < 0 < high  # no difference the calls can see


def test_turning_resume_off_changed_nothing():
    low, high = bootstrap_difference_interval(stops("ch07-e"),
                                              stops("ch07-f"))
    assert low < 0 < high


def test_no_arm_ever_resumed():
    for run in ("ch07-a", "ch07-b", "ch07-c", "ch07-d", "ch07-e", "ch07-f",
                "ch07-g-mhm", "ch07-g-real"):
        assert not any(resumed(c) for c in read(f"runs/{run}"))


def test_counting_words_stops_the_backchannel_and_costs_a_second():
    assert never_stopped("ch07-g-mhm")
    real = statistics.median(stops("ch07-g-real"))
    assert round(real, 3) == 1.781
    assert real - statistics.median(stops("ch07-b")) > 1.3


def test_the_warmup_holds_the_first_interruptions_to_one_moment():
    """Cutting in at 0.5 s and at 1.5 s ends at the same instant.

    On the agent's own clock that instant is 3.0 s after it started
    speaking, which is `aec_warmup_duration`.
    """
    for run in ("ch07-warmup-0.5", "ch07-warmup-1.5"):
        traces = [s for s in runlog.read(f"runs/{run}/stages.jsonl")
                  if s.get("stage") == "trace"]
        for call in read(f"runs/{run}"):
            mine = [t for t in traces if t["room"] == call["room"]]
            spoke = min(t["at"] for t in mine
                        if t["event"] == "agent speaking")
            quiet = min(t["at"] for t in mine
                        if t["event"] == "agent listening"
                        and t["at"] > spoke)
            assert 2.95 < quiet - spoke < 3.05


def test_the_whole_answer_is_handed_over_at_once():
    """Cancelling the code that makes audio cannot stop anything."""
    traces = [s for s in runlog.read("runs/ch07-a/stages.jsonl")
              if s.get("stage") == "trace"]
    for room in {t["room"] for t in traces}:
        mine = [t for t in traces if t["room"] == room]
        created = [t["at"] for t in mine if t["event"] == "speech created"]
        sent = [t for t in mine if t["event"] == "answer frames sent"]
        if not created or not sent:
            continue
        assert sent[0]["whole"]
        assert sent[0]["seconds"] > 22        # the entire answer
        assert sent[0]["at"] - created[0] < 1  # in under a second
