"""Pin the Chapter 10 results for a tool that takes three seconds."""

import statistics

from voicelab import ledger, runlog
from voicelab.stats import bootstrap_difference_interval
from waiting import calls_of, longest_quiet, traced


def ttfa(run):
    return [c["ttfa_s"] for c in calls_of(f"runs/{run}") if "ttfa_s" in c]


def test_a_three_second_tool_makes_a_much_longer_silence():
    waits = ttfa("ch10-silent")
    assert len(waits) == 3
    assert round(statistics.median(waits), 3) == 6.735
    # The tool is three seconds of it, and not the largest part.
    assert statistics.median(waits) > 2 * 3.0


def test_filler_halves_the_silence_without_moving_the_answer():
    silent, filler = ttfa("ch10-silent"), ttfa("ch10-filler")
    assert round(statistics.median(filler), 3) == 3.625
    low, high = bootstrap_difference_interval(silent, filler)
    assert high < 0  # the caller hears something sooner
    assert (round(low, 3), round(high, 3)) == (-3.297, -2.547)
    # And afterwards there is still a gap, where the answer used to be.
    gaps = [c["quiet_s"] for c in calls_of("runs/ch10-filler")]
    assert all(g and max(g) > 0.8 for g in gaps)


def test_hanging_up_does_not_stop_the_booking():
    """Three callers left early and all three were booked."""
    rows = ledger.entries("runs/ch10-hangup/ledger.jsonl")
    assert len(rows) == 3
    for call in calls_of("runs/ch10-hangup"):
        left = call["speech_end_wall"] + call["hung_up_after_s"]
        done = traced("runs/ch10-hangup", call["room"], "tool finished")
        assert done and done[0]["at"] > left  # it finished after they went
        assert any(r["room"] == call["room"] for r in rows)


def test_cancellable_did_not_cancel_anything():
    """The flag gives the model a cancel button, not the caller."""
    rows = ledger.entries("runs/ch10-cancel/ledger.jsonl")
    assert len(rows) == 6  # two per call, not one
    days = {r["day"].strip().lower() for r in rows}
    assert days == {"thursday", "friday"}
    for call in calls_of("runs/ch10-cancel"):
        started = traced("runs/ch10-cancel", call["room"], "tool called")
        finished = traced("runs/ch10-cancel", call["room"], "tool finished")
        assert len(started) == 2 and len(finished) == 2
        # The first booking ran its full three seconds after the caller
        # had already started talking over it.
        assert finished[0]["at"] - started[0]["at"] > 2.9
        assert call["interrupt_start_wall"] < finished[0]["at"]


def test_the_model_was_never_asked_while_the_tool_ran():
    """So it could not have cancelled, whatever it might have chosen.

    The trace records no function calls, so the absence of a cancel is
    not evidence. What is evidence is the timing: the tool finished
    before the next inference started, on every call.
    """
    for call in calls_of("runs/ch10-cancel"):
        finished = traced("runs/ch10-cancel", call["room"],
                          "tool finished")[0]["at"]
        thinking = [t["at"] for t in
                    traced("runs/ch10-cancel", call["room"],
                           "agent thinking") if t["at"] > finished]
        assert thinking and min(thinking) > finished


def test_marking_the_tool_cancellable_did_not_save_the_hangups():
    """The source says teardown drops cancellable work. It did not."""
    off = ledger.entries("runs/ch10-hangup/ledger.jsonl")
    on = ledger.entries("runs/ch10-hangup-cancellable/ledger.jsonl")
    assert len(off) == 3 and len(on) == 3
    for call in calls_of("runs/ch10-hangup-cancellable"):
        left = call["speech_end_wall"] + call["hung_up_after_s"]
        done = traced("runs/ch10-hangup-cancellable", call["room"],
                      "tool finished")
        assert done and done[0]["at"] > left


def test_longest_quiet_counts_the_wait_before_any_sound():
    call = {"ttfa_s": 6.735}
    assert longest_quiet(call) == 6.735
    call = {"ttfa_s": 3.6, "quiet_s": [0.89, 1.14]}
    assert longest_quiet(call) == 3.6
    assert longest_quiet({"quiet_s": [0.5]}) == 0.5
    assert longest_quiet({}) == 0.0


def test_every_run_used_a_three_second_tool():
    for run in ("ch10-silent", "ch10-filler", "ch10-cancel", "ch10-hangup",
                "ch10-hangup-cancellable"):
        config = [r for r in runlog.read(f"runs/{run}/stages.jsonl")
                  if r["stage"] == "config" and "tool_delay" in r]
        assert config and config[0]["tool_delay"] == 3.0
