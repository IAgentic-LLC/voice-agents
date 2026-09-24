"""Chapter 21: a handoff, by itself, does not know how many handoffs
came before it.

Each handoff builds a fresh `Agent`. Nothing about that object
remembers whether it is the first stop or the fifth, unless a count
is threaded through the same way Chapter 19 threads chat context
through by hand. This is that count.
"""

MAX_HANDOFFS = 2


def next_bounce_count(count: int) -> int:
    """The count the next agent in a handoff should be built with."""
    return count + 1


def too_many_handoffs(count: int) -> bool:
    """Whether a handoff should be allowed to happen at all."""
    return count >= MAX_HANDOFFS
