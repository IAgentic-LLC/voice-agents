"""Chapter 29: the load test report reads real trial rows and stays
inside the book's own column limit doing it."""

import os

from voicelab import runlog

import load_test_report


def test_reports_joined_and_ttfa_medians(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    run = "run"
    os.mkdir(run)
    rows = [
        {"call": 1, "ok": True, "join_s": 3.0, "ttfa_s": 1.5},
        {"call": 2, "ok": True, "join_s": 5.0, "ttfa_s": 2.0},
        {"call": 3, "ok": False, "error": "agent did not join"},
    ]
    for row in rows:
        runlog.append(f"{run}/trials.jsonl", row)

    load_test_report.main([run])

    out = capsys.readouterr().out
    assert "2 of 3" in out
    assert "4.000s" in out
    assert "1.750s" in out
    for line in out.splitlines():
        assert len(line) <= 78, line
