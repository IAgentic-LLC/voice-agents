"""Chapter 27: the timeline report reads a real Chapter 10 call and
correctly names both the raw biggest gap and the real tool wait,
which are two different spans."""

import timeline_report


def test_the_biggest_raw_gap_is_not_the_real_tool_wait(capsys):
    timeline_report.main("runs/ch10-filler", "call-be4d237a")

    out = capsys.readouterr().out
    assert 'biggest raw gap: 3.618s, between "agent speaking"' in out
    assert "tool called to tool finished: 2.992s" in out
    for line in out.splitlines():
        assert len(line) <= 78, line


def test_an_unknown_room_says_so(capsys):
    timeline_report.main("runs/ch10-filler", "no-such-room")

    assert "no events found" in capsys.readouterr().out
