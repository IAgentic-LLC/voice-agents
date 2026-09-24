"""Chapter 26: the two real leaderboards refuse in the two different
ways this chapter claims, and stay inside the book's column limit
doing it."""

import leaderboard_report


def test_the_voice_stack_leaderboard_finds_no_stable_winner(capsys):
    leaderboard_report.voice_stack_leaderboard()

    out = capsys.readouterr().out
    assert "cascaded   clean" in out
    assert "realtime   clean" in out
    assert "winner: none, ranking depends on the weighting used" in out
    for line in out.splitlines():
        assert len(line) <= 78, line


def test_the_routing_leaderboard_disqualifies_the_broken_run(capsys):
    leaderboard_report.routing_leaderboard()

    out = capsys.readouterr().out
    assert "routing-broken   disqualified" in out
    assert "routing-fixed    clean" in out
    assert "winner: routing-fixed (the only qualified candidate)" in out
    for line in out.splitlines():
        assert len(line) <= 78, line
