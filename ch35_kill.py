"""Chapter 35: kill the worker container mid-call, for real, with an
explicit non-blocking kill and wall-clock timestamps on both sides,
so the sequence of events is unambiguous afterward."""
import asyncio
import os
import time
from pathlib import Path

from dotenv import dotenv_values

OCI_ENV = dotenv_values(Path(__file__).resolve().parent / "deploy" / "oci" / ".env")
os.environ["LIVEKIT_URL"] = OCI_ENV["LIVEKIT_URL"]
os.environ["LIVEKIT_API_KEY"] = OCI_ENV["LIVEKIT_API_KEY"]
os.environ["LIVEKIT_API_SECRET"] = OCI_ENV["LIVEKIT_API_SECRET"]

from caller import one_call  # noqa: E402


async def kill_midway():
    await asyncio.sleep(5.0)
    print(f"KILL issued at wall clock {time.time():.3f}")
    proc = await asyncio.create_subprocess_exec(
        "ssh", "-i", "/c/Users/HomePC/.ssh/voice_agents_oci",
        "ubuntu@130.61.18.181",
        "docker kill studio-worker; date +%s.%N; docker ps -a --format "
        "'{{.Names}}: {{.Status}}' | grep studio-worker:",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    print("kill result:", out.decode(), err.decode())
    print(f"KILL confirmed at wall clock {time.time():.3f}")


async def main() -> None:
    t0 = time.time()
    print(f"call dispatch starting at wall clock {t0:.3f}")
    call, _ = await asyncio.gather(
        one_call(1, "dynabook", "runs/ch35-kill-midcall",
                "audio/ch09/plain.wav", listen_s=25.0, hangup_s=25.0,
                org="livedemo"),
        kill_midway(),
        return_exceptions=True,
    )
    print("call result:", call)


if __name__ == "__main__":
    asyncio.run(main())
