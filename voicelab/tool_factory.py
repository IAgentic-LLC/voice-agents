"""Chapter 31: the same tools Chapters 9 and 18 built, by name,
so an `AgentVersion` can choose which ones a caller gets without
any of this book's own code changing.

Every factory takes the same three arguments a hardcoded agent's
own closures already took, `ledger_path`, `room`, `stages`, and
returns one real `@function_tool`. Adding a new tool to a version
means adding one entry here, never patching an agent script.
"""

import time

from livekit.agents import RunContext, function_tool

from voicelab import ledger, refund, runlog


def make_book_callback(ledger_path: str, room: str, stages: str):
    @function_tool(on_duplicate="reject", duplicate_scope="name_and_args")
    async def book_callback(ctx: RunContext, day: str, time_of_day: str
                            ) -> str:
        """Book a callback for the caller.

        Args:
            day: the day of the week, such as Thursday
            time_of_day: the time, such as 2 pm
        """
        key = f"{room}:{day.strip().lower()}:{time_of_day.strip().lower()}"
        booked = ledger.attempt(ledger_path, key, "book_callback",
                                room=room, day=day, time_of_day=time_of_day)
        runlog.append(stages, {"stage": "trace", "room": room,
                               "event": "book_callback", "day": day,
                               "time_of_day": time_of_day, "at": time.time()})
        if booked["committed_now"]:
            return f"Booked for {day} at {time_of_day}."
        return "That callback was already booked. Nothing was changed."

    return book_callback


def make_issue_refund(ledger_path: str, room: str, stages: str):
    @function_tool
    async def issue_refund(ctx: RunContext, order_number: str) -> str:
        """Issue a refund for an order.

        Args:
            order_number: the order number the caller gives you
        """
        result = refund.issue(ledger_path, order_number)
        runlog.append(stages, {"stage": "trace", "room": room,
                               "event": "issue_refund",
                               "order_number": order_number,
                               "result": result, "at": time.time()})
        if not result["ok"]:
            return f"I couldn't refund that order: {result['reason']}."
        amount = result["order"]["amount"]
        return f"Refunded ${amount:.2f} for order {order_number}."

    return issue_refund


TOOL_FACTORIES = {
    "book_callback": make_book_callback,
    "issue_refund": make_issue_refund,
}


def build_tools(names: list[str], ledger_path: str, room: str, stages: str):
    unknown = [n for n in names if n not in TOOL_FACTORIES]
    if unknown:
        raise ValueError(f"no such tool(s): {unknown}")
    return [TOOL_FACTORIES[name](ledger_path, room, stages) for name in names]
