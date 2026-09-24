"""Chapter 21: the bounce count is the whole guard, pinned on its own
before any live call depends on it."""

from voicelab import routing


def test_the_count_climbs_by_one_each_handoff():
    assert routing.next_bounce_count(0) == 1
    assert routing.next_bounce_count(1) == 2


def test_a_fresh_agent_is_never_too_many():
    assert routing.too_many_handoffs(0) is False


def test_the_guard_trips_at_the_configured_maximum():
    assert routing.too_many_handoffs(routing.MAX_HANDOFFS) is True
    assert routing.too_many_handoffs(routing.MAX_HANDOFFS - 1) is False
