"""Chapter 25: rules a real system must never break, checked the
same way across every recorded run this book has, not written once
and trusted forever.

An invariant here is not a preference about style. It is a fact
about the system's own contract, and a single violation, anywhere,
in any run, is real evidence the contract was broken at least once.
"""

import re

from voicelab import knowledge, orders, runlog

_HYPHENATED = [p for p in knowledge.PASSAGES if "-" in p]
ID_PATTERN = re.compile("|".join(
    [rf"\b{re.escape(p)}\b" for p in _HYPHENATED]
    + [rf"\[{re.escape(p)}\]" for p in knowledge.PASSAGES]
))


def no_passage_id_spoken_aloud(stages_path: str) -> list[dict]:
    """A passage id is for the log, not the caller's ear (Chapter 11)."""
    return [
        row for row in runlog.read(stages_path)
        if row.get("event") == "assistant said"
        and ID_PATTERN.search(row.get("text", ""))
    ]


def every_refund_matches_its_real_order(ledger_path: str) -> list[dict]:
    """A ledger's own refund amount must equal the real order's real
    amount, never whatever a caller asked for (Chapters 18, 20, 23)."""
    violations = []
    for row in runlog.read(ledger_path):
        if row.get("action") != "refund":
            continue
        order = orders.find(row.get("order_id", ""))
        if order is None or row.get("amount") != order["amount"]:
            violations.append(row)
    return violations


def no_run_exceeds_the_handoff_cap(stages_path: str, max_handoffs: int = 2
                                   ) -> list[dict]:
    """No single call ever hands off more than the configured maximum
    (Chapter 21). A run above the cap means the guard that call was
    supposed to have was either missing or turned off."""
    handoffs = [
        row for row in runlog.read(stages_path)
        if row.get("event") == "handoff requested"
    ]
    return handoffs[max_handoffs:] if len(handoffs) > max_handoffs else []
