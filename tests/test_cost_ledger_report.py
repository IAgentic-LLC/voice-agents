"""Chapter 29: the cost ledger report reads the real ch08 runs and
prices them by the minute and by the successful task, not the call."""

import cost_ledger_report


def test_builds_a_real_ledger_from_the_ch08_runs():
    cascaded = cost_ledger_report.build_ledger("runs/ch08-cascaded")
    realtime = cost_ledger_report.build_ledger("runs/ch08-realtime")

    assert cascaded.total_minutes > 0
    assert realtime.total_minutes > 0
    assert cascaded.cost_per_minute < realtime.cost_per_minute
    assert cascaded.cost_per_successful_task < realtime.cost_per_successful_task


def test_main_stays_inside_the_books_column_limit(capsys):
    cost_ledger_report.main(["runs/ch08-cascaded", "runs/ch08-realtime"])

    out = capsys.readouterr().out
    assert "cost/minute" in out
    assert "cost/success" in out
    for line in out.splitlines():
        assert len(line) <= 78, line
