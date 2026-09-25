"""Chapter 34: one running worker, two real calls, two different
organizations. `AGENT_ORG` alone would not do this: LiveKit
dispatches by agent_name only, so two workers registered under the
same name are interchangeable to it. Real per-tenant routing for a
shared worker has to come from the call's own dispatch metadata,
read fresh per call, the same discipline this book has used for
`run_dir` since Chapter 1.

    uv run tenant_call_demo.py runs/ch34-acme-call runs/ch34-globex-call
"""

import asyncio
import sys

from caller import one_call
from voicelab.registry import create_version, current_version, deploy
from voicelab.tenants import add_member, create_org

DB = "runs/registry.db"
AGENT_NAME = "support"


def seed() -> None:
    create_org(DB, "acme", "Acme Corp")
    create_org(DB, "globex", "Globex Inc")
    add_member(DB, "acme", "auth0|acme-demo", "owner")
    add_member(DB, "globex", "auth0|globex-demo", "owner")

    v = create_version(
        DB, "acme", AGENT_NAME,
        instructions="You book callbacks for Acme Corp, and only Acme Corp.",
        model="gemini-3.5-flash-lite", tools=["book_callback"],
        based_on=current_version(DB, "acme", AGENT_NAME),
    )
    deploy(DB, "acme", AGENT_NAME, stable_version=v.version)

    v = create_version(
        DB, "globex", AGENT_NAME,
        instructions=(
            "You book callbacks for Globex Inc, and only Globex Inc. "
            "Mention Globex's own return policy if it comes up."
        ),
        model="gemini-3.5-flash-lite", tools=["book_callback"],
        based_on=current_version(DB, "globex", AGENT_NAME),
    )
    deploy(DB, "globex", AGENT_NAME, stable_version=v.version)


def main(acme_run: str, globex_run: str) -> None:
    seed()
    print("seeded acme and globex, each with their own real support agent")

    asyncio.run(one_call(1, AGENT_NAME, acme_run, org="acme", listen_s=6.0))
    print(f"real call placed for acme, recorded in {acme_run}")

    asyncio.run(
        one_call(1, AGENT_NAME, globex_run, org="globex", listen_s=6.0)
    )
    print(f"real call placed for globex, recorded in {globex_run}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
