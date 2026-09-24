"""Chapter 28: what a bounded retry buys, and what a breaker adds
on top of it, against one scripted flaky dependency.

The dependency here is scripted, not live: it fails the first two
times a run calls it, then recovers, on purpose, so the same three
outcomes below are reproducible on every run rather than depending
on a real service's mood that day.

    uv run resilience_report.py
"""

from voicelab.resilience import Breaker, GaveUp, call_with_retries


def flaky(fails_first: int):
    calls = {"n": 0}

    def attempt():
        calls["n"] += 1
        if calls["n"] <= fails_first:
            raise ConnectionError("booking service timed out")
        return "booked"

    return attempt, calls


def main() -> None:
    attempt, calls = flaky(fails_first=2)
    try:
        call_with_retries(attempt, attempts=1)
    except GaveUp:
        print(f"no retry: gave up after {calls['n']} call, "
              f"caller hears a failure")

    attempt, calls = flaky(fails_first=2)
    result = call_with_retries(attempt, attempts=3)
    print(f"bounded retry: {result} on call {calls['n']} of 3")

    breaker = Breaker(threshold=3, window_s=60, cooldown_s=30)
    for t, ok in [(0.0, False), (1.0, False), (2.0, False)]:
        breaker.record_failure(t) if not ok else breaker.record_success()
    print(f"breaker open right after 3 failures: {breaker.is_open(3.0)}")
    print(f"breaker open 30s later, cooldown elapsed: "
          f"{breaker.is_open(33.0)}")


if __name__ == "__main__":
    main()
