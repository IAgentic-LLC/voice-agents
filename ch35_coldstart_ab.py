"""Chapter 35: repeated real calls against the pre-fix worker code
(`dynabookbefore`) and the post-fix worker code (`dynabook`), both
against the same OCI server, both voice on, three trials each, to
compare the disclosed cold-start bug before and after on the same
box, not across Windows and Linux.

    uv run ch35_coldstart_ab.py
"""

import asyncio
import os
from pathlib import Path

from dotenv import dotenv_values

OCI_ENV = dotenv_values(Path(__file__).resolve().parent / "deploy" / "oci" / ".env")
os.environ["LIVEKIT_URL"] = OCI_ENV["LIVEKIT_URL"]
os.environ["LIVEKIT_API_KEY"] = OCI_ENV["LIVEKIT_API_KEY"]
os.environ["LIVEKIT_API_SECRET"] = OCI_ENV["LIVEKIT_API_SECRET"]

from caller import one_call  # noqa: E402


async def main() -> None:
    for i in range(1, 4):
        print(f"--- before (unfixed) trial {i} ---")
        result = await one_call(
            i, "dynabookbefore", "runs/ch35-coldstart-before",
            "audio/ch09/plain.wav", listen_s=20.0, org="livedemo",
        )
        print(result)

    for i in range(1, 4):
        print(f"--- after (prewarmed) trial {i} ---")
        result = await one_call(
            i, "dynabook", "runs/ch35-coldstart-after",
            "audio/ch09/plain.wav", listen_s=20.0, org="livedemo",
        )
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
