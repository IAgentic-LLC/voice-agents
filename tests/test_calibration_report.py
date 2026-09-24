"""Chapter 24: the calibration report flags every real disagreement
and stays inside the book's own column limit doing it."""

import calibration_report


def test_reports_every_disagreement(capsys):
    calibration_report.main()

    out = capsys.readouterr().out
    assert "disagreements: 5" in out
    assert out.count("MISCALIBRATED") == 5
    for line in out.splitlines():
        assert len(line) <= 78, line
