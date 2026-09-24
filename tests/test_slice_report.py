"""Chapter 24: the slice report reads Chapter 11's own real runs and
finds the same concentrated failure by hand-computation."""

import slice_report


def test_the_aggregate_hides_a_failure_concentrated_in_one_task(capsys):
    slice_report.main(["runs/ch11-plain", "runs/ch11-spoken",
                       "runs/ch11-one"])

    out = capsys.readouterr().out
    assert "aggregate: 13 of 15" in out
    assert "return   1 of 3" in out
    assert "refund   3 of 3" in out
    for line in out.splitlines():
        assert len(line) <= 78, line
