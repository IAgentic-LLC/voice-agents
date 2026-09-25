"""Chapter 35: 1, then 5, concurrent real calls against the
OCI-hosted worker, to see how a free-tier 2 OCPU box actually
behaves under load its idle pool (num_idle_processes=2) was not
sized for.

    uv run ch35_concurrency.py
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

OCI_ENV = dotenv_values(Path(__file__).resolve().parent / "deploy" / "oci" / ".env")
os.environ["LIVEKIT_URL"] = OCI_ENV["LIVEKIT_URL"]
os.environ["LIVEKIT_API_KEY"] = OCI_ENV["LIVEKIT_API_KEY"]
os.environ["LIVEKIT_API_SECRET"] = OCI_ENV["LIVEKIT_API_SECRET"]

from caller import one_call  # noqa: E402


async def wave(n: int, run_dir: str) -> None:
    results = await asyncio.gather(*[
        one_call(i, "dynabook", f"{run_dir}/call{i}",
                 "audio/ch09/plain.wav", listen_s=20.0, org="livedemo")
        for i in range(1, n + 1)
    ], return_exceptions=True)
    ok = sum(1 for r in results if isinstance(r, dict) and r.get("ok"))
    print(f"n={n}: {ok}/{n} ok")
    for r in results:
        print(r)


async def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    await wave(n, f"runs/ch35-concurrency-{n}")


if __name__ == "__main__":
    asyncio.run(main())
