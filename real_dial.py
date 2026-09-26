"""Placing a real outbound call to a real phone, through the Studio,
against a version a caller just built and deployed there.

Chapter 15's own `outbound.py` already proved `create_sip_participant`
against the self-hosted server in `deploy/oci`. Chapter 32's own
Playground only ever called into the local dev room. This reuses both
real mechanisms together: dispatch the agent to a fresh room the same
way `caller.py`'s own `one_call` does, then dial a real number into
that same room, both against the OCI server explicitly, not whichever
server this process's own environment happens to default to.

    uv run real_dial.py +49...
"""

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

from dotenv import dotenv_values
from livekit import api
from livekit.protocol import sip as sip_proto

from voicelab import runlog


def _oci_env() -> dict:
    """The OCI server's own LiveKit and SIP settings.

    A local run finds these in `deploy/oci/.env`, next to this file
    on disk. A containerized run, on the OCI box itself, has no such
    file relative to `real_dial.py`, since the image never bakes in
    a dotenv file, only a real process environment set by the
    deployment's own `env_file`. Falling back to `os.environ` for
    whatever the dotenv file does not supply is what makes the same
    module work in both places, rather than assuming one on-disk
    layout that only one of them actually has.
    """
    from_file = dotenv_values(
        Path(__file__).resolve().parent / "deploy" / "oci" / ".env")
    return {**os.environ, **from_file}


OCI_ENV = _oci_env()


async def dial_real_number(number: str, agent_name: str, org: str,
                           run_dir: str, wait_s: float = 45.0) -> dict:
    stages = f"{run_dir}/stages.jsonl"
    lk = api.LiveKitAPI(
        OCI_ENV["LIVEKIT_URL"].replace("ws", "http", 1),
        OCI_ENV["LIVEKIT_API_KEY"], OCI_ENV["LIVEKIT_API_SECRET"],
    )
    room_name = f"real-call-{uuid.uuid4().hex[:8]}"
    identity = f"outbound-{int(time.time())}"
    runlog.append(stages, {"stage": "config", "room": room_name,
                           "number": number, "agent_name": agent_name,
                           "org_id": org})
    try:
        await lk.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=agent_name, room=room_name,
                metadata=json.dumps({"run_dir": run_dir, "org_id": org}),
            )
        )
        runlog.append(stages, {"stage": "call_state", "event": "dispatched"})
        info = await lk.sip.create_sip_participant(
            sip_proto.CreateSIPParticipantRequest(
                sip_trunk_id=OCI_ENV["SIP_OUTBOUND_TRUNK_ID"],
                sip_call_to=number, room_name=room_name,
                participant_identity=identity, wait_until_answered=True,
            ),
            timeout=wait_s,
        )
        runlog.append(stages, {"stage": "call_state", "event": "answered",
                               "call_id": info.sip_call_id})
        return {"ok": True, "room": room_name, "call_id": info.sip_call_id}
    except Exception as exc:  # noqa: BLE001 - report, never hide
        runlog.append(stages, {"stage": "call_state", "event": "error",
                               "error": str(exc)})
        return {"ok": False, "room": room_name, "error": str(exc)}
    finally:
        await lk.aclose()


if __name__ == "__main__":
    number = sys.argv[1]
    result = asyncio.run(dial_real_number(
        number, os.environ.get("AGENT_NAME", "dynabook"),
        os.environ.get("AGENT_ORG", "default"), "runs/real-call-cli",
    ))
    print(result)
