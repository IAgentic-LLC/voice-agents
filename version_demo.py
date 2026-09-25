"""Chapter 31: seeds two real versions of the same agent, one with
a tool its own instructions never mention.

    uv run version_demo.py seed-v1
    uv run version_demo.py seed-v2
"""

import sys

from voicelab.registry import create_version, current_version

DB = "runs/registry.db"
ORG = "default"
AGENT_NAME = "dynabook"


def seed_v1():
    return create_version(
        DB, ORG, AGENT_NAME,
        instructions="You are a support assistant who books callbacks.",
        model="gemini-3.5-flash-lite",
        tools=["book_callback"],
        based_on=current_version(DB, ORG, AGENT_NAME),
    )


def seed_v2():
    return create_version(
        DB, ORG, AGENT_NAME,
        instructions=(
            "You are a support assistant who books callbacks and issues "
            "refunds when a caller gives an order number."
        ),
        model="gemini-3.5-flash-lite",
        tools=["book_callback", "issue_refund"],
        based_on=current_version(DB, ORG, AGENT_NAME),
    )


if __name__ == "__main__":
    command = sys.argv[1]
    version = {"seed-v1": seed_v1, "seed-v2": seed_v2}[command]()
    print(f"{AGENT_NAME} is now at version {version.version}")
