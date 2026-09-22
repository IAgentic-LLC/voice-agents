"""Pin the Chapter 9 results, and the mechanism the runs never triggered."""

import statistics

from actions import report, traced
from voicelab import ledger, runlog


def bookings(run):
    return ledger.entries(f"runs/{run}/ledger.jsonl")


def test_the_plain_request_books_once_per_call():
    got = report("runs/ch09-off-plain")
    assert got["calls"] == 2
    assert got["booked"] == 2  # one each
    assert got["days"] == {"thursday"}


def test_the_wrong_booking_beat_the_correction_by_milliseconds():
    """The correction's first loud frame is at -1.83 s in the recording."""
    for call in runlog.read("runs/ch09-off-split/trials.jsonl"):
        t0 = call["speech_end_wall"]
        first = min(t["at"] - t0 for t in
                    traced("runs/ch09-off-split", call["room"],
                           ("tool called",)))
        assert -1.83 < first < -1.78  # after the caller began correcting


def test_a_correction_across_a_pause_books_twice():
    """The failure this chapter is about."""
    got = report("runs/ch09-off-split")
    assert got["calls"] == 2
    assert got["tool_calls"] == 4 and got["booked"] == 4  # two each
    assert got["days"] == {"thursday", "friday"}
    # And the caller was told about one of them.
    rows = runlog.read("runs/ch09-off-split/trials.jsonl")
    said = traced("runs/ch09-off-split", rows[0]["room"],
                  ("assistant said",))
    spoken = " ".join(t["text"] for t in said).lower()
    assert "friday" in spoken and "thursday" not in spoken


def test_the_same_correction_at_a_natural_pace_books_once():
    """The control: without the long pause, no confirmation is needed."""
    got = report("runs/ch09-off-natural")
    assert got["calls"] == 2
    assert got["tool_calls"] == 2 and got["booked"] == 2  # one each
    assert got["days"] == {"friday"}   # the day the caller ended on
    assert got["asked"] == 0           # and it never asked


def test_the_corrected_request_confirmed_books_once_on_the_right_day():
    """The outcome the chapter asks for, end to end."""
    got = report("runs/ch09-on-split-yes")
    assert got["calls"] == 2
    assert got["tool_calls"] == 2 and got["booked"] == 2
    assert got["days"] == {"friday"}
    assert got["asked"] == 2


def test_reading_it_back_books_nothing_until_the_caller_agrees():
    asked = report("runs/ch09-on-split")
    assert asked["booked"] == 0 and asked["tool_calls"] == 0
    assert asked["asked"] == 2  # it asked on both calls
    agreed = report("runs/ch09-on-plain")
    assert agreed["booked"] == 2 and agreed["asked"] == 2
    assert agreed["days"] == {"thursday"}


def test_confirming_costs_one_turn():
    rows = runlog.read("runs/ch09-on-plain/trials.jsonl")
    waits = []
    for call in rows:
        tools = [t["at"] for t in
                 traced("runs/ch09-on-plain", call["room"],
                        ("tool called",))]
        waits.append(min(tools) - call["interrupt_start_wall"])
    assert 3.0 < statistics.median(waits) < 4.0


def test_the_model_did_not_call_the_tool_twice_for_one_request():
    """It answered from memory instead. Good behaviour, not a guarantee."""
    got = report("runs/ch09-off-twice")
    assert got["tool_calls"] == 2 and got["booked"] == 2  # one each


def test_no_two_tool_calls_in_any_run_shared_a_key():
    """So the ledger's key was never the thing that stopped a repeat."""
    for run in ("ch09-off-natural", "ch09-off-plain", "ch09-off-split",
                "ch09-off-twice", "ch09-on-split", "ch09-on-split-yes",
                "ch09-on-plain"):
        keys = [row["key"] for row in bookings(run)]
        assert len(keys) == len(set(keys))


def test_the_key_refuses_a_repeat(tmp_path):
    """The mechanism the live runs never needed."""
    path = str(tmp_path / "ledger.jsonl")
    key = "room-1:friday:2 pm"
    first = ledger.attempt(path, key, "book_callback", day="Friday")
    again = ledger.attempt(path, key, "book_callback", day="Friday")
    assert first["committed_now"] and not again["committed_now"]
    assert again["day"] == "Friday"      # it returns the original
    assert len(ledger.entries(path)) == 1  # and writes nothing new


def test_a_different_day_is_a_different_action(tmp_path):
    """Which is why a key cannot save you from a correction."""
    path = str(tmp_path / "ledger.jsonl")
    ledger.attempt(path, "room-1:thursday:2 pm", "book", day="Thursday")
    ledger.attempt(path, "room-1:friday:2 pm", "book", day="Friday")
    assert len(ledger.entries(path)) == 2
