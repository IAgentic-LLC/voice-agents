"""Chapter 28: the resilience report's own printed output, checked
against the exact wording and numbers the chapter quotes."""

import resilience_report


def test_the_report_shows_all_three_outcomes(capsys):
    resilience_report.main()

    out = capsys.readouterr().out
    assert "no retry: gave up after 1 call" in out
    assert "bounded retry: booked on call 3 of 3" in out
    assert "breaker open right after 3 failures: True" in out
    assert "breaker open 30s later, cooldown elapsed: False" in out
    for line in out.splitlines():
        assert len(line) <= 78, line
