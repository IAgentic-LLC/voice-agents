"""Chapter 32: pin what a real click in a real browser, against
the real Studio, actually produced. `studio_e2e.py` placed this
live, through the UI's own Run call button, not a mocked fetch."""

from voicelab import runlog


def test_a_real_browser_click_placed_a_real_call():
    [record] = runlog.read("runs/ch32-playground/stages.jsonl")
    assert record["event"] == "studio playground call"
    assert record["agent"] == "studiotest"
    assert record["room"].startswith("call-")
    assert record["join_s"] is not None


def test_a_real_stale_write_showed_a_real_conflict_in_the_ui():
    [record] = runlog.read("runs/ch32-conflict/stages.jsonl")
    assert record["event"] == "studio conflict"
    assert record["background_writer_version"] == 2
    assert record["ui_error"] == (
        "Someone else already wrote a newer version. Reload and try again."
    )
