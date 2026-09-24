"""Chapter 28: a bounded retry recovers from a flaky dependency; a
breaker stops retrying one that is clearly down, then closes again
once it has had time to recover."""

import pytest

from voicelab.resilience import Breaker, GaveUp, call_with_retries


def flaky(fails_first: int):
    calls = {"n": 0}

    def attempt():
        calls["n"] += 1
        if calls["n"] <= fails_first:
            raise ConnectionError("booking service timed out")
        return "booked"

    return attempt, calls


def test_a_single_attempt_never_retries():
    attempt, calls = flaky(fails_first=1)

    with pytest.raises(GaveUp):
        call_with_retries(attempt, attempts=1)
    assert calls["n"] == 1


def test_a_bounded_retry_recovers_from_a_flaky_dependency():
    attempt, calls = flaky(fails_first=2)

    result = call_with_retries(attempt, attempts=3)

    assert result == "booked"
    assert calls["n"] == 3


def test_giving_up_chains_the_real_last_error():
    attempt, _ = flaky(fails_first=5)

    with pytest.raises(GaveUp) as excinfo:
        call_with_retries(attempt, attempts=3)
    assert isinstance(excinfo.value.__cause__, ConnectionError)


def test_a_breaker_stays_closed_below_its_threshold():
    breaker = Breaker(threshold=3, window_s=60, cooldown_s=30)

    breaker.record_failure(now=0.0)
    breaker.record_failure(now=1.0)

    assert not breaker.is_open(now=2.0)


def test_a_breaker_opens_once_failures_reach_the_threshold():
    breaker = Breaker(threshold=3, window_s=60, cooldown_s=30)

    for t in (0.0, 1.0, 2.0):
        breaker.record_failure(now=t)

    assert breaker.is_open(now=3.0)


def test_a_breaker_closes_again_after_its_cooldown():
    breaker = Breaker(threshold=3, window_s=60, cooldown_s=30)

    for t in (0.0, 1.0, 2.0):
        breaker.record_failure(now=t)
    assert breaker.is_open(now=3.0)

    assert not breaker.is_open(now=33.0)


def test_failures_outside_the_window_do_not_count():
    breaker = Breaker(threshold=3, window_s=10, cooldown_s=30)

    breaker.record_failure(now=0.0)
    breaker.record_failure(now=1.0)

    assert not breaker.is_open(now=15.0)
    breaker.record_failure(now=15.0)
    assert not breaker.is_open(now=15.0)


def test_a_success_clears_the_breaker():
    breaker = Breaker(threshold=3, window_s=60, cooldown_s=30)

    for t in (0.0, 1.0, 2.0):
        breaker.record_failure(now=t)
    breaker.record_success()

    assert not breaker.is_open(now=3.0)
