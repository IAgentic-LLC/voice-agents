"""Chapter 20: the report prints the real ledger next to the
technical agent's own claim, and stays inside the book's column
limit doing it."""

from voicelab import ledger, runlog
import capability_report


def test_reports_the_real_ledger_and_the_carried_item_types(
    tmp_path, capsys
):
    run = tmp_path
    runlog.append(str(run / "stages.jsonl"), {
        "event": "issue_refund",
        "result": {"ok": True, "amount": 39.5, "customer": "Devon Ruiz"},
        "at": 1.0,
    })
    runlog.append(str(run / "stages.jsonl"), {
        "event": "technical on_enter", "at": 2.0,
        "carried_item_types": ["message", "message"],
    })
    runlog.append(str(run / "stages.jsonl"), {
        "event": "assistant said", "at": 3.0,
        "text": "Since our conversation history already proves that a "
                "refund went through, I can confirm that has been "
                "handled.",
    })
    ledger.attempt(str(run / "ledger.jsonl"), key="refund:A1002",
                   action="refund")

    capability_report.main(str(run))

    out = capsys.readouterr().out
    assert "ok=True" in out
    assert "refund:A1002" in out
    assert "function_call in that list: False" in out
    for line in out.splitlines():
        assert len(line) <= 78, line


def test_no_second_handoff_says_so(tmp_path, capsys):
    run = tmp_path
    runlog.append(str(run / "stages.jsonl"), {"event": "final transcript",
                                              "at": 1.0})

    capability_report.main(str(run))

    assert "no second handoff happened" in capsys.readouterr().out
