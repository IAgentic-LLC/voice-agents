"""Chapter 29: the kill report reads the two real kill runs and
prints what each one actually did to the call."""

import kill_report


def test_the_two_real_kills_show_two_different_outcomes(capsys):
    kill_report.main(["runs/ch29-kill-wrapper", "runs/ch29-kill-tree"])

    out = capsys.readouterr().out
    assert "wrapper: killed pids [24224]" in out
    assert "agent finished its reply" in out
    assert "the caller's room never reported a disconnect" in out
    assert "tree: killed pids [33732, 34072, 28624]" in out
    assert "the agent never finished its reply" in out
    assert "disconnected_after_kill_s: 20.839" in out
    for line in out.splitlines():
        assert len(line) <= 78, line
