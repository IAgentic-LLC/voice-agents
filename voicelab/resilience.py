"""Chapter 28: a bounded retry, and a breaker that stops retrying
once a dependency has clearly stopped working.

Both are pure. Neither one sleeps, dials a real dependency, or
reads a real clock; the caller supplies `now` and the attempt
itself, the same discipline Chapter 15's guards already used.
"""

from dataclasses import dataclass, field


class GaveUp(Exception):
    """Every attempt failed. The last real error is `__cause__`."""


def call_with_retries(attempt, *, attempts: int):
    """Call `attempt()` up to `attempts` times, stopping at the
    first success. Raises GaveUp, chained to the last real error,
    if every attempt fails."""
    last = None
    for _ in range(attempts):
        try:
            return attempt()
        except Exception as e:
            last = e
    raise GaveUp() from last


@dataclass
class Breaker:
    """Opens once `threshold` failures have landed inside the last
    `window_s`, and stays open for `cooldown_s` after the most
    recent one, so a dependency that is clearly down stops being
    retried on every single call while it recovers."""

    threshold: int
    window_s: float
    cooldown_s: float
    failures: list[float] = field(default_factory=list)

    def record_failure(self, now: float) -> None:
        self.failures.append(now)

    def record_success(self) -> None:
        self.failures.clear()

    def is_open(self, now: float) -> bool:
        self.failures = [t for t in self.failures if now - t < self.window_s]
        if len(self.failures) < self.threshold:
            return False
        return now - self.failures[-1] < self.cooldown_s
