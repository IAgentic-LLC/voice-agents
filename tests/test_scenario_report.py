"""Chapter 23: the scenario report reads the real ledger next to
the transcript, and stays inside the book's column limit doing it."""

from voicelab import ledger, runlog
import scenario_report


def test_reports_the_transcript_and_the_real_ledger_entry(tmp_path, capsys):
    run = tmp_path
    runlog.append(str(run / "stages.jsonl"), {
        "event": "user said", "at": 1.0,
        "text": "Hi, this is Devon Ruiz. Please refund order A1001.",
    })
    runlog.append(str(run / "stages.jsonl"), {
        "event": "issue_refund", "order_number": "A1001", "at": 2.0,
    })
    runlog.append(str(run / "stages.jsonl"), {
        "event": "assistant said", "at": 3.0,
        "text": "I have successfully issued a refund for order A1001.",
    })
    ledger.attempt(str(run / "ledger.jsonl"), key="refund:A1001",
                   action="refund", order_id="A1001", amount=24.99,
                   customer="Priya Shah")

    scenario_report.main(str(run))

    out = capsys.readouterr().out
    assert "Devon Ruiz" in out
    assert "order_number=A1001" in out
    assert "customer=Priya Shah" in out
    for line in out.splitlines():
        assert len(line) <= 78, line


def test_no_ledger_entry_says_so(tmp_path, capsys):
    run = tmp_path
    runlog.append(str(run / "stages.jsonl"), {
        "event": "user said", "at": 1.0, "text": "hello",
    })

    scenario_report.main(str(run))

    assert "no entry was written" in capsys.readouterr().out
