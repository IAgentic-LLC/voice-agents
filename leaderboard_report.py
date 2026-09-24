"""Chapter 26: two real leaderboards, run the same way, that answer
their own question differently.

    uv run leaderboard_report.py

The voice-stack leaderboard has two candidates that both clear
every invariant, then finds no stable winner once they are scored.
The routing leaderboard has one candidate that never clears the
gate at all, and refuses to rank it against anything.
"""

from profile_report import build_profile
from voicelab.leaderboard import Candidate, stable_winner, violation_count


def voice_stack_leaderboard() -> None:
    print("voice stack leaderboard")
    candidates = [
        Candidate(name="cascaded", run="runs/ch08-cascaded"),
        Candidate(name="realtime", run="runs/ch08-realtime"),
    ]
    profiles = []
    for c in candidates:
        v = violation_count(c)
        status = "disqualified" if v else "clean"
        print(f"  {c.name:10s} {status} ({v} violation(s))")
        if v == 0:
            profiles.append(build_profile(c.run))

    winner = stable_winner(profiles) if len(profiles) > 1 else None
    if winner:
        print(f"  winner: {winner}")
    else:
        print("  winner: none, ranking depends on the weighting used")


def routing_leaderboard() -> None:
    print("routing leaderboard")
    candidates = [
        Candidate(name="routing-broken", run="runs/ch21-broken"),
        Candidate(name="routing-fixed", run="runs/ch21-fixed"),
    ]
    qualified = []
    for c in candidates:
        v = violation_count(c)
        status = "disqualified" if v else "clean"
        print(f"  {c.name:16s} {status} ({v} violation(s))")
        if v == 0:
            qualified.append(c.name)

    if len(qualified) == 1:
        print(f"  winner: {qualified[0]} (the only qualified candidate)")
    elif len(qualified) == 0:
        print("  winner: none, every candidate was disqualified")
    else:
        print(f"  winner: none, {len(qualified)} candidates qualified, "
              f"not scored here")


if __name__ == "__main__":
    voice_stack_leaderboard()
    print()
    routing_leaderboard()
