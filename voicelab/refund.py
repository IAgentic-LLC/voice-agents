"""Chapter 18: the power this chapter's agent was given, unscoped.

`issue` checks exactly one thing the policy actually says (the
30-day window) and nothing this chapter's own thesis is about: it
never checks that the caller asking for a refund is the customer
the order belongs to. That is not a bug in this function. It is the
function this chapter is arguing an agent should not have been
handed without a boundary around it.
"""

from voicelab import ledger, orders


def issue(ledger_path: str, order_id: str) -> dict:
    order = orders.find(order_id)
    if order is None:
        return {"ok": False, "reason": "no such order"}
    if not orders.eligible(order):
        return {"ok": False, "reason": "outside the 30-day window",
                "order": order}
    result = ledger.attempt(
        ledger_path, key=f"refund:{order_id.strip().upper()}",
        action="refund", order_id=order_id.strip().upper(),
        amount=order["amount"], customer=order["customer"],
    )
    return {"ok": True, **result, "order": order}
