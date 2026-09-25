"""Chapter 33: a stable version, a canary with a real operator's
typo in it, and a rollback, against one real worker that never
changes.

    uv run canary_demo.py runs/ch33-stable runs/ch33-canary runs/ch33-rolled-back

Every phase runs real live calls through `dynamic_agent.py`. The
worker's own routing, not this script, decides which version each
call gets, by reading whatever `deploy` last wrote. The canary
version's own tool list has a genuine typo, `isue_refund`, so a
fraction of calls in the canary phase hit a real crash the worker
itself logs, not a simulated one.
"""

import asyncio
import sys

from caller import one_call
from voicelab.registry import create_version, current_version, deploy

DB = "runs/registry.db"
ORG = "default"
AGENT_NAME = "canarybook"
CALLS = 12
LISTEN_S = 4.0
CANARY_PERCENT = 30.0


def seed() -> tuple[int, int]:
    v1 = create_version(
        DB, ORG, AGENT_NAME,
        instructions="You are a support assistant who books callbacks.",
        model="gemini-3.5-flash-lite", tools=["book_callback"],
        based_on=current_version(DB, ORG, AGENT_NAME),
    )
    v2 = create_version(
        DB, ORG, AGENT_NAME,
        instructions=(
            "You are a support assistant who books callbacks and issues "
            "refunds when a caller gives an order number."
        ),
        model="gemini-3.5-flash-lite",
        tools=["book_callback", "isue_refund"],  # a real operator's typo
        based_on=v1.version,
    )
    return v1.version, v2.version


async def run_calls(run_dir: str, n: int) -> None:
    """One call at a time. Building a fresh model client per call
    blocks this worker's event loop for several real seconds
    (Chapters 31 and 32 already saw this); running calls concurrently
    stacks those blocks and starves the room connection's own
    heartbeat until the whole worker panics, not just one call."""
    for i in range(1, n + 1):
        await one_call(i, AGENT_NAME, run_dir, listen_s=LISTEN_S)


def main(stable_run: str, canary_run: str, rolled_back_run: str) -> None:
    v1, v2 = seed()

    deploy(DB, ORG, AGENT_NAME, stable_version=v1)
    print(f"deployed: 100% stable on v{v1}")
    asyncio.run(run_calls(stable_run, CALLS))

    deploy(DB, ORG, AGENT_NAME, stable_version=v1, canary_version=v2,
          canary_percent=CANARY_PERCENT)
    print(f"deployed: {CANARY_PERCENT:.0f}% canary on v{v2} (has a typo'd "
          f"tool), rest stable on v{v1}")
    asyncio.run(run_calls(canary_run, CALLS))

    deploy(DB, ORG, AGENT_NAME, stable_version=v1)
    print(f"rolled back: 100% stable on v{v1} again, no canary function ran")
    asyncio.run(run_calls(rolled_back_run, CALLS))


if __name__ == "__main__":
    main(*sys.argv[1:4])
