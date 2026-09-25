"""Chapter 32: the real HTTP surface the Voice Agent Studio talks
to. Every route is a thin wrapper around Chapter 31's own registry
and tool factory; nothing here duplicates that logic.

    uv run uvicorn studio_api:app --port 8032

Settings (environment variables):
    STUDIO_DB     the registry's own SQLite file
                  (default runs/registry.db)
"""

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from caller import one_call
from voicelab.registry import (
    StaleVersionError, create_version, current_version, get_version,
    list_versions,
)
from voicelab.tool_factory import TOOL_FACTORIES

STUDIO_DB = os.environ.get("STUDIO_DB", "runs/registry.db")

app = FastAPI(title="Voice Agent Studio API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
    allow_headers=["*"],
)


class VersionOut(BaseModel):
    agent_name: str
    version: int
    instructions: str
    model: str
    tools: list[str]
    created_at: float


class NewVersion(BaseModel):
    instructions: str
    model: str
    tools: list[str]
    based_on: int


class PlaygroundCall(BaseModel):
    question_audio: str
    listen_s: float = 20.0


class PlaygroundResult(BaseModel):
    ok: bool
    room: str
    error: str | None = None
    join_s: float | None = None
    ttfa_s: float | None = None


def _out(v) -> VersionOut:
    return VersionOut(agent_name=v.agent_name, version=v.version,
                      instructions=v.instructions, model=v.model,
                      tools=v.tools, created_at=v.created_at)


@app.get("/api/tools")
def api_tools() -> list[str]:
    return sorted(TOOL_FACTORIES)


@app.get("/api/agents/{name}/versions")
def api_list_versions(name: str) -> list[VersionOut]:
    return [_out(v) for v in list_versions(STUDIO_DB, name)]


@app.get("/api/agents/{name}/versions/{version}")
def api_get_version(name: str, version: int) -> VersionOut:
    v = get_version(STUDIO_DB, name, version)
    if v is None:
        raise HTTPException(404, f"{name} has no version {version}")
    return _out(v)


@app.post("/api/agents/{name}/versions", status_code=201)
def api_create_version(name: str, body: NewVersion) -> VersionOut:
    unknown = [t for t in body.tools if t not in TOOL_FACTORIES]
    if unknown:
        raise HTTPException(422, f"no such tool(s): {unknown}")
    try:
        v = create_version(
            STUDIO_DB, name, instructions=body.instructions,
            model=body.model, tools=body.tools, based_on=body.based_on,
        )
    except StaleVersionError as exc:
        raise HTTPException(409, str(exc))
    return _out(v)


@app.post("/api/agents/{name}/playground/call")
async def api_playground_call(name: str, body: PlaygroundCall
                              ) -> PlaygroundResult:
    if current_version(STUDIO_DB, name) == 0:
        raise HTTPException(404, f"{name} has no version to call")
    run_dir = f"runs/studio-playground/{name}"
    result = await one_call(1, name, run_dir, body.question_audio,
                            listen_s=body.listen_s)
    return PlaygroundResult(
        ok=result.get("ok", False), room=result["room"],
        error=result.get("error"), join_s=result.get("join_s"),
        ttfa_s=result.get("ttfa_s"),
    )
