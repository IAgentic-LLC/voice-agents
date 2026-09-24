"""Chapter 25: the gate report reads real run directories under
runs/, reports every one with a violation, and blocks the release
when it finds any."""

import gate_report


def test_the_real_history_flags_exactly_ch21_broken(capsys):
    gate_report.main()

    out = capsys.readouterr().out
    assert "runs/ch21-broken:" in out
    assert "82 handoff(s) over cap" in out
    assert "release: BLOCKED" in out
    for line in out.splitlines():
        assert len(line) <= 78, line
