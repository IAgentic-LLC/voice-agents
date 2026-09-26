"""Chapter 31: the same tools Chapters 9 and 18 built, by name,
so an `AgentVersion` can choose which ones a caller gets without
any of this book's own code changing.

Every factory takes the same three arguments a hardcoded agent's
own closures already took, `ledger_path`, `room`, `stages`, and
returns one real `@function_tool`. Adding a new tool to a version
means adding one entry here, never patching an agent script.

Chapter 35: `room` is the real `rtc.Room`, not just its name, so a
tool that needs to act on the live call, not merely log against it,
has something to act on. Every existing factory still only reads
`room.name`; `make_transfer_to_human` is the first one that needs
the object itself.
"""

import os
import time

from livekit.agents import RunContext, function_tool

from voicelab import consent, ledger, refund, runlog, transfer


def make_book_callback(ledger_path: str, room, stages: str):
    @function_tool(on_duplicate="reject", duplicate_scope="name_and_args")
    async def book_callback(ctx: RunContext, day: str, time_of_day: str
                            ) -> str:
        """Book a callback for the caller.

        Args:
            day: the day of the week, such as Thursday
            time_of_day: the time, such as 2 pm
        """
        key = f"{room.name}:{day.strip().lower()}:{time_of_day.strip().lower()}"
        booked = ledger.attempt(ledger_path, key, "book_callback",
                                room=room.name, day=day, time_of_day=time_of_day)
        runlog.append(stages, {"stage": "trace", "room": room.name,
                               "event": "book_callback", "day": day,
                               "time_of_day": time_of_day, "at": time.time()})
        if booked["committed_now"]:
            return f"Booked for {day} at {time_of_day}."
        return "That callback was already booked. Nothing was changed."

    return book_callback


def make_issue_refund(ledger_path: str, room, stages: str):
    @function_tool
    async def issue_refund(ctx: RunContext, order_number: str) -> str:
        """Issue a refund for an order.

        Args:
            order_number: the order number the caller gives you
        """
        result = refund.issue(ledger_path, order_number)
        runlog.append(stages, {"stage": "trace", "room": room.name,
                               "event": "issue_refund",
                               "order_number": order_number,
                               "result": result, "at": time.time()})
        if not result["ok"]:
            return f"I couldn't refund that order: {result['reason']}."
        amount = result["order"]["amount"]
        return f"Refunded ${amount:.2f} for order {order_number}."

    return issue_refund


async def run_transfer_to_human(room, stages: str) -> str:
    """The real logic behind the `transfer_to_human` tool, pulled out
    of the `@function_tool` closure so it can be called directly by a
    test, the same reason Chapter 8's cascaded and realtime agents
    both import one shared `policy.py` instead of duplicating logic
    a decorator would otherwise hide.
    """
    target = os.environ.get("TRANSFER_TO_NUMBER")
    if not target:
        return "I'm not able to transfer calls right now."
    consent_path = os.environ.get("TRANSFER_CONSENT_PATH",
                                  "runs/transfer-consent.jsonl")
    dnc_path = os.environ.get("TRANSFER_DNC_PATH",
                              "runs/transfer-dnc.txt")
    if consent.on_do_not_call_list(dnc_path, target):
        return "I'm not able to transfer this call."
    if not consent.has_consent(consent_path, target):
        return "I'm not able to transfer this call."
    trunk_id = os.environ.get("SIP_OUTBOUND_TRUNK_ID")
    runlog.append(stages, {"stage": "trace", "room": room.name,
                           "event": "transfer_requested", "at": time.time()})
    result = await transfer.warm_transfer(room, target, trunk_id)
    runlog.append(stages, {"stage": "trace", "room": room.name,
                           "event": "transfer_result", "result": result,
                           "at": time.time()})
    if not result["ok"]:
        return "I couldn't reach anyone to transfer you to right now."
    return "You're connected. I'll step back now."


def make_transfer_to_human(ledger_path: str, room, stages: str):
    """Warm-transfer the caller to a real human, the same mechanism
    Chapter 17 proved: dial a second real number into the caller's
    own room and wait for their audio to actually arrive before
    telling the caller they are connected.

    The destination is an operator setting, `TRANSFER_TO_NUMBER`, not
    a number the caller supplies: a real support line a business
    transfers to, never an arbitrary number a caller's own words
    could point this at. Consent and the do-not-call list are
    checked the same way Chapter 15's own outbound calls already
    are, against `TRANSFER_CONSENT_PATH` and `TRANSFER_DNC_PATH`,
    because a warm transfer is still this system placing a real call
    to someone who never dialed in.
    """
    @function_tool
    async def transfer_to_human(ctx: RunContext) -> str:
        """Connect the caller to a real human, when they ask to speak
        to a person rather than continue with you."""
        return await run_transfer_to_human(room, stages)

    return transfer_to_human


TOOL_FACTORIES = {
    "book_callback": make_book_callback,
    "issue_refund": make_issue_refund,
    "transfer_to_human": make_transfer_to_human,
}


def build_tools(names: list[str], ledger_path: str, room, stages: str):
    unknown = [n for n in names if n not in TOOL_FACTORIES]
    if unknown:
        raise ValueError(f"no such tool(s): {unknown}")
    return [TOOL_FACTORIES[name](ledger_path, room, stages) for name in names]
