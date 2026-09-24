"""Chapter 18: orders real enough to have a wrong one refunded.

A fixed, small order book, not a database, but real in the one way
that matters for this chapter: each order belongs to a specific
customer, and nothing about a spoken order number proves who is
speaking.
"""

ORDERS = {
    "A1001": {"customer": "Priya Shah", "item": "wireless mouse",
             "amount": 24.99, "days_since_delivery": 3},
    "A1002": {"customer": "Devon Ruiz", "item": "desk lamp",
             "amount": 39.50, "days_since_delivery": 12},
    "A1003": {"customer": "Priya Shah", "item": "usb hub",
             "amount": 18.00, "days_since_delivery": 45},
}


def find(order_id: str) -> dict | None:
    return ORDERS.get(order_id.strip().upper())


def eligible(order: dict) -> bool:
    """The same 30-day window Chapter 8's policy states out loud."""
    return order["days_since_delivery"] <= 30
