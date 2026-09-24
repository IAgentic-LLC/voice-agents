"""Chapter 22: what a good voice agent means is not one number.

Task success, latency and cost each answer a different question.
Collapsing them into a single score buries whichever one the weights
happen to undervalue, and it is worse than that when one of the
numbers being averaged in is itself incomplete: Chapter 8's own cost
figure for the cascaded stack counts only 1 of its 3 real stages,
because the speech plugins report seconds and characters, not the
tokens Google actually bills. A missing measurement is not the same
fact as a low one, and a single score cannot tell them apart.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    run: str
    right: int
    total: int
    ttfa_median_s: float
    cost_per_call: float
    priced_stages: int
    total_stages: int
    total_cost: float = 0.0
    total_minutes: float = 0.0

    @property
    def task_success(self) -> float:
        return self.right / self.total

    @property
    def cost_is_known(self) -> bool:
        return self.priced_stages == self.total_stages

    @property
    def cost_per_minute(self) -> float | None:
        """Chapter 29: the same total cost, divided by real minutes of
        call time instead of by call count."""
        return (self.total_cost / self.total_minutes
                if self.total_minutes else None)

    @property
    def cost_per_successful_task(self) -> float | None:
        """Chapter 29: what one correct answer cost, on average, not
        what one call cost regardless of whether it was right."""
        return self.total_cost / self.right if self.right else None


def one_score(profile: Profile, *, weight_speed: float, weight_cost: float,
              max_wait_s: float, max_cost: float) -> float:
    """A single weighted score, built the way a leaderboard usually
    is, so its own blind spot is visible rather than argued about.

    `weight_speed` and `weight_cost` must each be within [0, 1] and
    sum to at most 1; whatever is left over weights task success.
    """
    speed = 1 - min(profile.ttfa_median_s / max_wait_s, 1.0)
    cost = 1 - min(profile.cost_per_call / max_cost, 1.0)
    weight_success = 1.0 - weight_speed - weight_cost
    return (weight_success * profile.task_success
            + weight_speed * speed
            + weight_cost * cost)
