"""Chapter 25: the gate report reads real run directories under
runs/, reports every one with a violation, and blocks the release
when it finds any. Chapter 30 adds a fourth check and a second real
run this book's own history was already carrying: ch28-plain."""

import gate_report


def test_the_real_history_flags_ch21_broken_and_ch28_plain(capsys):
    gate_report.main()

    out = capsys.readouterr().out
    assert "runs/ch21-broken:" in out
    assert "82 handoff(s) over cap" in out
    assert "runs/ch28-plain:" in out
    assert "1 generic error(s)" in out
    assert "release: BLOCKED" in out
    for line in out.splitlines():
        assert len(line) <= 78, line
