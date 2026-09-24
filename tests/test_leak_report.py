"""Chapter 18: the leak-report printer stays inside 78 columns."""

from voicelab import runlog
import leak_report


def test_no_printed_line_exceeds_the_books_column_limit(tmp_path, capsys):
    path = tmp_path / "stages.jsonl"
    runlog.append(str(path), {"event": "user speaking"})
    runlog.append(str(path), {
        "event": "final transcript",
        "text": "Hi, can you book me a callback for Thursday at 2:00 "
                "p.m.? Also, can you refund order A1002 please?",
    })
    runlog.append(str(path), {
        "event": "issue_refund", "order_number": "A1002",
        "result": {"ok": True, "amount": 39.5, "customer": "Devon Ruiz"},
    })

    leak_report.main(str(tmp_path))

    for line in capsys.readouterr().out.splitlines():
        assert len(line) <= 78, line
