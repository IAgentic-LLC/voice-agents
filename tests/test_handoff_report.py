"""Chapter 19: the report reads the handoff's own two events, not
the whole trace."""

from voicelab import runlog
import handoff_report


def test_reports_latency_and_the_first_thing_said_after(tmp_path, capsys):
    path = tmp_path / "stages.jsonl"
    runlog.append(str(path), {
        "event": "handoff requested", "carry_context": True, "at": 10.000,
    })
    runlog.append(str(path), {
        "event": "handoff complete", "at": 10.350,
    })
    runlog.append(str(path), {
        "event": "assistant said", "at": 11.000,
        "text": "I see your order A1002, let's continue with that.",
    })

    handoff_report.main(str(tmp_path))

    out = capsys.readouterr().out
    assert "carry_context: True" in out
    assert "handoff latency: 0.350s" in out
    assert "A1002" in out


def test_no_handoff_in_the_run_says_so(tmp_path, capsys):
    path = tmp_path / "stages.jsonl"
    runlog.append(str(path), {"event": "final transcript", "at": 1.0})

    handoff_report.main(str(tmp_path))

    assert "no handoff was requested" in capsys.readouterr().out


def test_a_long_spoken_line_wraps_within_the_books_column_limit(
    tmp_path, capsys
):
    path = tmp_path / "stages.jsonl"
    runlog.append(str(path), {
        "event": "handoff requested", "carry_context": False, "at": 5.0,
    })
    runlog.append(str(path), {"event": "handoff complete", "at": 5.022})
    runlog.append(str(path), {
        "event": "assistant said", "at": 5.5,
        "text": "I don't have your order number yet. Could you please "
                "provide your order number before we proceed?",
    })

    handoff_report.main(str(tmp_path))

    for line in capsys.readouterr().out.splitlines():
        assert len(line) <= 78, line
