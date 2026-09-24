"""Chapter 22: a score profile keeps what one score would hide.
Chapter 29 adds cost per minute and per successful task."""

from voicelab.profile import Profile, one_score


def test_cost_is_known_reports_the_real_priced_fraction():
    fully_priced = Profile(run="a", right=10, total=10, ttfa_median_s=1.0,
                           cost_per_call=0.01, priced_stages=1,
                           total_stages=1)
    partly_priced = Profile(run="b", right=10, total=10, ttfa_median_s=1.0,
                            cost_per_call=0.01, priced_stages=1,
                            total_stages=3)
    assert fully_priced.cost_is_known is True
    assert partly_priced.cost_is_known is False


def test_the_same_two_runs_can_flip_winner_depending_on_weights():
    slow_but_cheap = Profile(run="cascaded", right=10, total=10,
                             ttfa_median_s=6.071, cost_per_call=0.00007,
                             priced_stages=1, total_stages=3)
    fast_but_pricier = Profile(run="realtime", right=10, total=10,
                               ttfa_median_s=1.523, cost_per_call=0.00243,
                               priced_stages=1, total_stages=1)
    max_wait = max(slow_but_cheap.ttfa_median_s, fast_but_pricier.ttfa_median_s)
    max_cost = max(slow_but_cheap.cost_per_call, fast_but_pricier.cost_per_call)

    speed_weighted = {
        p.run: one_score(p, weight_speed=0.5, weight_cost=0.2,
                         max_wait_s=max_wait, max_cost=max_cost)
        for p in (slow_but_cheap, fast_but_pricier)
    }
    cost_weighted = {
        p.run: one_score(p, weight_speed=0.1, weight_cost=0.7,
                         max_wait_s=max_wait, max_cost=max_cost)
        for p in (slow_but_cheap, fast_but_pricier)
    }

    assert max(speed_weighted, key=speed_weighted.get) == "realtime"
    assert max(cost_weighted, key=cost_weighted.get) == "cascaded"


def test_cost_per_minute_divides_total_cost_by_total_minutes():
    p = Profile(run="a", right=8, total=10, ttfa_median_s=1.0,
               cost_per_call=0.001, priced_stages=1, total_stages=1,
               total_cost=0.02, total_minutes=4.0)

    assert p.cost_per_minute == 0.005


def test_cost_per_successful_task_divides_total_cost_by_right():
    p = Profile(run="a", right=8, total=10, ttfa_median_s=1.0,
               cost_per_call=0.001, priced_stages=1, total_stages=1,
               total_cost=0.02, total_minutes=4.0)

    assert p.cost_per_successful_task == 0.0025


def test_both_new_properties_are_none_without_the_data_for_them():
    p = Profile(run="a", right=0, total=0, ttfa_median_s=1.0,
               cost_per_call=0.0, priced_stages=0, total_stages=0)

    assert p.cost_per_minute is None
    assert p.cost_per_successful_task is None
