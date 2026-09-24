"""Chapter 26: the leaderboard's two refusals, pinned on constructed
data before either is trusted against this book's real history."""

from voicelab.profile import Profile
from voicelab.leaderboard import Candidate, stable_winner, violation_count
from voicelab import runlog


def test_a_clean_run_has_no_violations(tmp_path):
    candidate = Candidate(name="clean", run=str(tmp_path))
    assert violation_count(candidate) == 0


def test_a_run_over_the_handoff_cap_is_a_violation(tmp_path):
    path = tmp_path / "stages.jsonl"
    for _ in range(3):
        runlog.append(str(path), {"event": "handoff requested"})
    candidate = Candidate(name="looped", run=str(tmp_path))
    assert violation_count(candidate) == 1


def test_a_stable_winner_is_named_when_every_weighting_agrees():
    dominant = Profile(run="a", right=10, total=10, ttfa_median_s=1.0,
                       cost_per_call=0.001, priced_stages=1,
                       total_stages=1)
    weak = Profile(run="b", right=5, total=10, ttfa_median_s=5.0,
                   cost_per_call=0.01, priced_stages=1, total_stages=1)
    assert stable_winner([dominant, weak]) == "a"


def test_no_winner_is_named_when_weightings_disagree():
    cascaded = Profile(run="cascaded", right=10, total=10,
                       ttfa_median_s=6.071, cost_per_call=0.00007,
                       priced_stages=1, total_stages=3)
    realtime = Profile(run="realtime", right=10, total=10,
                       ttfa_median_s=1.523, cost_per_call=0.00243,
                       priced_stages=1, total_stages=1)
    assert stable_winner([cascaded, realtime]) is None
