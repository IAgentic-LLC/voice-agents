"""Chapter 31: the version report reads the two real calls this
chapter placed and shows what changed with no code deploy at all."""

import version_report


def test_the_two_real_versions_show_two_different_capabilities(capsys):
    version_report.main(["runs/ch31-v1", "runs/ch31-v2"])

    out = capsys.readouterr().out
    assert "version 1, tools=['book_callback']" in out
    assert "unable to process refunds directly" in out
    assert "version 2, tools=['book_callback', 'issue_refund']" in out
    assert "successfully issued a refund" in out
    for line in out.splitlines():
        assert len(line) <= 78, line
