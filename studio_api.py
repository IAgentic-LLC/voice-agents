"""Chapter 32: the real HTTP surface the Voice Agent Studio talks
to. Every route is a thin wrapper around Chapter 31's own registry
and tool factory; nothing here duplicates that logic.

Chapter 34 adds a real caller identity (Auth0, verified per request)
and a real organization boundary: every agent route is scoped under
`/api/orgs/{org_id}/...`, and a caller's role in that specific
organization, not just a valid token, decides what they can do.

    uv run uvicorn studio_api:app --port 8032

Settings (environment variables):
    STUDIO_DB     the registry's own SQLite file
                  (default runs/registry.db)
"""

import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from caller import one_call
from voicelab.auth import Principal, register_auth_exception_handlers, verify_token
from voicelab.registry import (
    StaleVersionError, create_version, current_deployment, current_version,
    deploy, get_version, list_versions,
)
from voicelab.tenants import (
    OrgExistsError, add_member, create_org, get_role, list_members,
    list_orgs_for_subject,
)
from voicelab.tool_factory import TOOL_FACTORIES

STUDIO_DB = os.environ.get("STUDIO_DB", "runs/registry.db")

ROLE_RANK = {"viewer": 0, "editor": 1, "owner": 2}

app = FastAPI(title="Voice Agent Studio API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
    allow_headers=["*"],
)
register_auth_exception_handlers(app)


def require_role(min_role: str):
    """A dependency that only lets a request through if the caller
    (a real, verified `Principal`) has at least `min_role` in the
    organization named by this route's own `org_id` path parameter.
    A caller with no membership at all is refused the same way as
    one with too low a role: neither can tell the difference between
    an organization that does not exist and one they are not in."""
    def dependency(org_id: str, principal: Principal = Depends(verify_token)
                  ) -> Principal:
        role = get_role(STUDIO_DB, org_id, principal.subject)
        if role is None:
            raise HTTPException(403, f"not a member of {org_id!r}")
        if ROLE_RANK[role] < ROLE_RANK[min_role]:
            raise HTTPException(
                403, f"requires role {min_role!r} or higher, has {role!r}"
            )
        return principal
    return dependency


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


class DeploymentOut(BaseModel):
    stable_version: int
    canary_version: int | None
    canary_percent: float
    created_at: float


class NewDeployment(BaseModel):
    stable_version: int
    canary_version: int | None = None
    canary_percent: float = 0.0


class NewOrg(BaseModel):
    org_id: str
    name: str


class OrgOut(BaseModel):
    org_id: str
    name: str
    created_at: float


class NewMember(BaseModel):
    subject: str
    role: str


class MemberOut(BaseModel):
    subject: str
    role: str
    created_at: float


class MyOrgOut(BaseModel):
    org_id: str
    role: str


def _out(v) -> VersionOut:
    return VersionOut(agent_name=v.agent_name, version=v.version,
                      instructions=v.instructions, model=v.model,
                      tools=v.tools, created_at=v.created_at)


@app.get("/api/tools")
def api_tools() -> list[str]:
    return sorted(TOOL_FACTORIES)


@app.get("/api/me/orgs")
def api_my_orgs(principal: Principal = Depends(verify_token)
                ) -> list[MyOrgOut]:
    """Which organizations this caller belongs to, and at what
    role, so the Studio can offer a real choice instead of asking
    the caller to already know an `org_id`."""
    return [MyOrgOut(org_id=m.org_id, role=m.role)
           for m in list_orgs_for_subject(STUDIO_DB, principal.subject)]


@app.post("/api/orgs", status_code=201)
def api_create_org(body: NewOrg, principal: Principal = Depends(verify_token)
                   ) -> OrgOut:
    """Anyone with a verified identity can create an organization;
    doing so makes them its first owner."""
    try:
        org = create_org(STUDIO_DB, body.org_id, body.name)
    except OrgExistsError as exc:
        raise HTTPException(409, str(exc))
    add_member(STUDIO_DB, body.org_id, principal.subject, "owner")
    return OrgOut(org_id=org.org_id, name=org.name, created_at=org.created_at)


@app.get("/api/orgs/{org_id}/members")
def api_list_members(org_id: str,
                     principal: Principal = Depends(require_role("viewer"))
                     ) -> list[MemberOut]:
    return [MemberOut(subject=m.subject, role=m.role, created_at=m.created_at)
           for m in list_members(STUDIO_DB, org_id)]


@app.post("/api/orgs/{org_id}/members", status_code=201)
def api_add_member(org_id: str, body: NewMember,
                   principal: Principal = Depends(require_role("owner"))
                   ) -> MemberOut:
    try:
        m = add_member(STUDIO_DB, org_id, body.subject, body.role)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return MemberOut(subject=m.subject, role=m.role, created_at=m.created_at)


@app.get("/api/orgs/{org_id}/agents/{name}/versions")
def api_list_versions(org_id: str, name: str,
                      principal: Principal = Depends(require_role("viewer"))
                      ) -> list[VersionOut]:
    return [_out(v) for v in list_versions(STUDIO_DB, org_id, name)]


@app.get("/api/orgs/{org_id}/agents/{name}/versions/{version}")
def api_get_version(org_id: str, name: str, version: int,
                    principal: Principal = Depends(require_role("viewer"))
                    ) -> VersionOut:
    v = get_version(STUDIO_DB, org_id, name, version)
    if v is None:
        raise HTTPException(404, f"{name} has no version {version}")
    return _out(v)


@app.post("/api/orgs/{org_id}/agents/{name}/versions", status_code=201)
def api_create_version(org_id: str, name: str, body: NewVersion,
                       principal: Principal = Depends(require_role("editor"))
                       ) -> VersionOut:
    unknown = [t for t in body.tools if t not in TOOL_FACTORIES]
    if unknown:
        raise HTTPException(422, f"no such tool(s): {unknown}")
    try:
        v = create_version(
            STUDIO_DB, org_id, name, instructions=body.instructions,
            model=body.model, tools=body.tools, based_on=body.based_on,
        )
    except StaleVersionError as exc:
        raise HTTPException(409, str(exc))
    return _out(v)


@app.get("/api/orgs/{org_id}/agents/{name}/deployment")
def api_get_deployment(org_id: str, name: str,
                       principal: Principal = Depends(require_role("viewer"))
                       ) -> DeploymentOut | None:
    d = current_deployment(STUDIO_DB, org_id, name)
    if d is None:
        return None
    return DeploymentOut(stable_version=d.stable_version,
                         canary_version=d.canary_version,
                         canary_percent=d.canary_percent,
                         created_at=d.created_at)


@app.post("/api/orgs/{org_id}/agents/{name}/deployment", status_code=201)
def api_deploy(org_id: str, name: str, body: NewDeployment,
              principal: Principal = Depends(require_role("editor"))
              ) -> DeploymentOut:
    try:
        d = deploy(STUDIO_DB, org_id, name, stable_version=body.stable_version,
                  canary_version=body.canary_version,
                  canary_percent=body.canary_percent)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return DeploymentOut(stable_version=d.stable_version,
                         canary_version=d.canary_version,
                         canary_percent=d.canary_percent,
                         created_at=d.created_at)


@app.post("/api/orgs/{org_id}/agents/{name}/playground/call")
async def api_playground_call(org_id: str, name: str, body: PlaygroundCall,
                               principal: Principal = Depends(
                                   require_role("editor"))
                               ) -> PlaygroundResult:
    if current_version(STUDIO_DB, org_id, name) == 0:
        raise HTTPException(404, f"{name} has no version to call")
    run_dir = f"runs/studio-playground/{org_id}/{name}"
    result = await one_call(1, name, run_dir, body.question_audio,
                            listen_s=body.listen_s)
    return PlaygroundResult(
        ok=result.get("ok", False), room=result["room"],
        error=result.get("error"), join_s=result.get("join_s"),
        ttfa_s=result.get("ttfa_s"),
    )
