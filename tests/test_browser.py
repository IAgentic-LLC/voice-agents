"""Pin what Chapter 3 says about the browser and the transport."""

from report import summarize
from voicelab import runlog


def test_browser_and_python_agree_from_the_end_of_speech():
    browser = summarize("runs/ch03-browser-realtime")
    python = summarize("runs/ch03-python-control")
    assert round(browser["ttfa_median"], 3) == 1.385
    assert round(python["ttfa_median"], 3) == 1.343
    assert abs(browser["ttfa_median"] - python["ttfa_median"]) < 0.05


def test_turning_off_audio_processing_did_not_help():
    raw = summarize("runs/ch03-browser-raw")
    assert raw["ttfa_median"] > 1.385


def test_transport_round_trip_is_a_fifth_of_a_second():
    python = summarize("runs/ch03-echo-python")
    browser = summarize("runs/ch03-echo-browser")
    assert round(python["echo_median"], 3) == 0.185
    assert round(browser["echo_median"], 3) == 0.195
    assert (browser["calls"], len(browser["echo"])) == (10, 8)


def test_no_microphone_on_a_page_that_is_not_secure():
    [record] = runlog.read("runs/ch03-not-secure/trials.jsonl")
    assert record["error"] == "not a secure context"
    assert record["secure"] is False
