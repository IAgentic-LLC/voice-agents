"""Chapter 33: the report only counts what each call's own worker
already wrote, correlated by room, nothing recomputed."""

from voicelab import runlog
import canary_report


def test_tally_counts_calls_per_lane_by_room(tmp_path):
    run = tmp_path / "run"
    for room, lane in [("call-1", "stable"), ("call-2", "stable"),
                       ("call-3", "canary")]:
        runlog.append(run / "stages.jsonl", {
            "stage": "config", "room": room, "lane": lane,
        })

    counts = canary_report.tally(str(run))
    assert counts == {
        "stable": {"calls": 2, "errors": 0},
        "canary": {"calls": 1, "errors": 0},
    }


def test_tally_counts_a_worker_error_against_its_own_calls_lane(tmp_path):
    run = tmp_path / "run"
    runlog.append(run / "stages.jsonl", {
        "stage": "config", "room": "call-1", "lane": "canary",
    })
    runlog.append(run / "stages.jsonl", {
        "stage": "worker_error", "room": "call-1", "lane": "canary",
        "error": "no such tool(s): ['isue_refund']",
    })

    counts = canary_report.tally(str(run))
    assert counts["canary"] == {"calls": 1, "errors": 1}


def test_tally_of_an_empty_run_is_empty(tmp_path):
    run = tmp_path / "run"
    assert canary_report.tally(str(run)) == {}


def test_main_prints_one_line_per_run(tmp_path, capsys):
    run = tmp_path / "run"
    runlog.append(run / "stages.jsonl", {
        "stage": "config", "room": "call-1", "lane": "stable",
    })

    canary_report.main([str(run)])

    out = capsys.readouterr().out
    assert "1 calls" in out
    assert len(out.splitlines()) == 1
