"""Small statistics used by every report in the book."""

import math
import random
import statistics


def wilson_interval(
    successes: int, n: int, z: float = 1.96
) -> tuple[float, float]:
    """95% Wilson score interval for a success rate."""
    if n == 0:
        return 0.0, 1.0
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    low = max(0.0, (centre - margin) / denom)
    high = min(1.0, (centre + margin) / denom)
    return low, high


def bootstrap_median_interval(
    values: list[float], reps: int = 10_000, seed: int = 0
) -> tuple[float, float]:
    """95% percentile bootstrap interval for the median.

    Resample the values with replacement, take the median each time, and
    keep the middle 95% of those medians. The seed is fixed so the book's
    numbers can be reproduced exactly.
    """
    rng = random.Random(seed)
    n = len(values)
    medians = sorted(
        statistics.median(rng.choices(values, k=n)) for _ in range(reps)
    )
    return medians[int(0.025 * reps)], medians[int(0.975 * reps) - 1]


def bootstrap_difference_interval(
    a: list[float], b: list[float], reps: int = 10_000, seed: int = 0
) -> tuple[float, float]:
    """95% bootstrap interval for median(b) - median(a).

    Resample each group on its own, take the difference of the two
    medians, and keep the middle 95% of those differences. If the interval
    does not include zero, the two groups really differ in the median.
    """
    rng = random.Random(seed)
    diffs = sorted(
        statistics.median(rng.choices(b, k=len(b)))
        - statistics.median(rng.choices(a, k=len(a)))
        for _ in range(reps)
    )
    return diffs[int(0.025 * reps)], diffs[int(0.975 * reps) - 1]
