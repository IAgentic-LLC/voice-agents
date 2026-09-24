"""Chapter 22: the profile report reads the real ch08 runs correctly
and stays inside the book's own column limit doing it."""

import profile_report


def test_builds_a_real_profile_from_the_ch08_runs():
    cascaded = profile_report.build_profile("runs/ch08-cascaded")
    realtime = profile_report.build_profile("runs/ch08-realtime")

    assert cascaded.task_success == 1.0
    assert realtime.task_success == 1.0
    assert cascaded.ttfa_median_s > realtime.ttfa_median_s
    assert cascaded.cost_is_known is False
    assert realtime.cost_is_known is True


def test_main_stays_inside_the_books_column_limit(capsys):
    profile_report.main(["runs/ch08-cascaded", "runs/ch08-realtime"])

    for line in capsys.readouterr().out.splitlines():
        assert len(line) <= 78, line
