"""Chapter 21: the report counts real handoffs and stays inside the
book's own column limit doing it."""

from voicelab import runlog
import routing_report


def test_counts_handoffs_and_reports_the_highest_bounce(tmp_path, capsys):
    path = tmp_path / "stages.jsonl"
    for n, to in enumerate(["support", "sales"]):
        runlog.append(str(path), {
            "event": "handoff requested", "to": to, "bounces": n,
            "at": float(n),
        })
    runlog.append(str(path), {
        "event": "assistant said", "at": 5.0,
        "text": "I can help you figure that out.",
    })

    routing_report.main(str(tmp_path))

    out = capsys.readouterr().out
    assert "handoffs: 2" in out
    assert "highest bounce count: 1" in out
    assert "blocked: 0" in out


def test_a_long_spoken_line_wraps_within_the_books_column_limit(
    tmp_path, capsys
):
    path = tmp_path / "stages.jsonl"
    runlog.append(str(path), {
        "event": "handoff requested", "to": "support", "bounces": 0,
        "at": 0.0,
    })
    runlog.append(str(path), {
        "event": "handoff blocked", "to": "sales", "bounces": 2, "at": 1.0,
    })
    runlog.append(str(path), {
        "event": "assistant said", "at": 2.0,
        "text": "I'm transferring you to our technical support team "
                "right now to help resolve that app crash and billing "
                "issue. Please hold on for just a moment.",
    })

    routing_report.main(str(tmp_path))

    for line in capsys.readouterr().out.splitlines():
        assert len(line) <= 78, line


def test_no_routing_events_says_so(tmp_path, capsys):
    path = tmp_path / "stages.jsonl"
    runlog.append(str(path), {"event": "final transcript", "at": 1.0})

    routing_report.main(str(tmp_path))

    assert "no routing events in this run" in capsys.readouterr().out
