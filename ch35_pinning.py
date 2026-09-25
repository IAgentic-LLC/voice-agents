"""Chapter 35: dispatch a real call under version 1, deploy version 2
while that call is still connected, and check whether the active
call's own agent kept speaking version 1's instructions throughout,
proof that dynamic_agent.py's entrypoint resolves a version once and
never rereads it mid-call.

    uv run ch35_pinning.py
"""

import asyncio
import os
import subprocess
from pathlib import Path

from dotenv import dotenv_values

OCI_ENV = dotenv_values(Path(__file__).resolve().parent / "deploy" / "oci" / ".env")
os.environ["LIVEKIT_URL"] = OCI_ENV["LIVEKIT_URL"]
os.environ["LIVEKIT_API_KEY"] = OCI_ENV["LIVEKIT_API_KEY"]
os.environ["LIVEKIT_API_SECRET"] = OCI_ENV["LIVEKIT_API_SECRET"]

from caller import one_call  # noqa: E402

DEPLOY_CMD = (
    'TOKEN=$(cat ~/studio/.token); '
    'curl -s -X POST http://127.0.0.1:8032/api/orgs/livedemo/agents/dynabook/deployment '
    '-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" '
    '-d \'{"stable_version":2,"canary_version":null,"canary_percent":0}\''
)


async def deploy_v2_midway():
    await asyncio.sleep(6.0)
    proc = subprocess.run(
        ["ssh", "-i", "/c/Users/HomePC/.ssh/voice_agents_oci",
         "ubuntu@130.61.18.181", DEPLOY_CMD],
        capture_output=True, text=True,
    )
    print("deploy-v2-while-in-flight:", proc.stdout, proc.stderr)


async def main() -> None:
    in_flight, fresh_after = await asyncio.gather(
        one_call(1, "dynabook", "runs/ch35-pin-in-flight",
                "audio/ch09/plain.wav", listen_s=20.0, hangup_s=18.0,
                org="livedemo"),
        deploy_v2_midway(),
    )
    print("in_flight_call:", in_flight)

    fresh = await one_call(1, "dynabook", "runs/ch35-pin-fresh-after",
                           "audio/ch09/plain.wav", listen_s=20.0,
                           org="livedemo")
    print("fresh_call_after_deploy:", fresh)


if __name__ == "__main__":
    asyncio.run(main())
