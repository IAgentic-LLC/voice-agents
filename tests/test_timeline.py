"""Chapter 27: the timeline functions, pinned on constructed data
before either is trusted against this book's real history."""

from voicelab import runlog
from voicelab.timeline import biggest_gap, paired_duration, timeline


def test_timeline_keeps_only_one_rooms_events_in_order(tmp_path):
    path = str(tmp_path / "stages.jsonl")
    runlog.append(path, {"room": "a", "at": 2.0, "event": "second"})
    runlog.append(path, {"room": "b", "at": 1.0, "event": "other room"})
    runlog.append(path, {"room": "a", "at": 1.0, "event": "first"})

    events = timeline(path, "a")

    assert [e["event"] for e in events] == ["first", "second"]


def test_biggest_gap_can_point_at_the_wrong_stage(tmp_path):
    """A long TTS playback span can outweigh a real tool wait in raw
    adjacency alone, exactly the failure this chapter's own real
    call showed."""
    path = str(tmp_path / "stages.jsonl")
    runlog.append(path, {"room": "a", "at": 0.0, "event": "tool called"})
    runlog.append(path, {"room": "a", "at": 3.0, "event": "tool finished"})
    runlog.append(path, {"room": "a", "at": 3.1, "event": "agent speaking"})
    runlog.append(path, {"room": "a", "at": 7.0, "event": "assistant said"})

    a, b, gap = biggest_gap(timeline(path, "a"))

    assert (a["event"], b["event"]) == ("agent speaking", "assistant said")
    assert gap == 3.9


def test_paired_duration_finds_the_real_tool_wait_by_name(tmp_path):
    path = str(tmp_path / "stages.jsonl")
    runlog.append(path, {"room": "a", "at": 0.0, "event": "tool called"})
    runlog.append(path, {"room": "a", "at": 3.0, "event": "tool finished"})
    runlog.append(path, {"room": "a", "at": 3.1, "event": "agent speaking"})
    runlog.append(path, {"room": "a", "at": 7.0, "event": "assistant said"})

    duration = paired_duration(timeline(path, "a"), "tool called",
                               "tool finished")

    assert duration == 3.0


def test_paired_duration_is_none_when_a_side_is_missing(tmp_path):
    path = str(tmp_path / "stages.jsonl")
    runlog.append(path, {"room": "a", "at": 0.0, "event": "tool called"})

    assert paired_duration(timeline(path, "a"), "tool called",
                           "tool finished") is None
