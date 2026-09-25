"""Chapter 32: the real HTTP surface the Studio talks to, checked
against a real (temporary) registry file and a mocked live call.
Chapter 34: every route now needs a verified identity and a real
role in the organization named by its own URL."""

from fastapi.testclient import TestClient

import studio_api
from voicelab.auth import Principal, verify_token

OWNER = "auth0|owner-1"
EDITOR = "auth0|editor-1"
VIEWER = "auth0|viewer-1"
OUTSIDER = "auth0|outsider-1"


def _as(subject: str) -> None:
    studio_api.app.dependency_overrides[verify_token] = (
        lambda: Principal(subject=subject)
    )


def client(tmp_path, monkeypatch):
    monkeypatch.setattr(studio_api, "STUDIO_DB", str(tmp_path / "r.db"))
    studio_api.app.dependency_overrides.clear()
    return TestClient(studio_api.app)


def _new_org(c, org_id="acme"):
    _as(OWNER)
    resp = c.post("/api/orgs", json={"org_id": org_id, "name": "Acme Corp"})
    assert resp.status_code == 201, resp.text
    c.post(f"/api/orgs/{org_id}/members",
          json={"subject": EDITOR, "role": "editor"})
    c.post(f"/api/orgs/{org_id}/members",
          json={"subject": VIEWER, "role": "viewer"})
    return org_id


def test_tools_lists_the_real_registered_factories(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    resp = c.get("/api/tools")
    assert resp.status_code == 200
    assert resp.json() == ["book_callback", "issue_refund"]


def test_creating_an_org_makes_the_creator_its_owner(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    org = _new_org(c)

    _as(OWNER)
    resp = c.get(f"/api/orgs/{org}/members")
    roles = {m["subject"]: m["role"] for m in resp.json()}
    assert roles[OWNER] == "owner"
    assert roles[EDITOR] == "editor"
    assert roles[VIEWER] == "viewer"


def test_my_orgs_lists_every_org_a_subject_belongs_to(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    _new_org(c, "acme")
    _new_org(c, "globex")

    _as(OWNER)
    resp = c.get("/api/me/orgs")
    orgs = {o["org_id"]: o["role"] for o in resp.json()}
    assert orgs == {"acme": "owner", "globex": "owner"}

    _as(EDITOR)
    resp = c.get("/api/me/orgs")
    orgs = {o["org_id"]: o["role"] for o in resp.json()}
    assert orgs == {"acme": "editor", "globex": "editor"}


def test_creating_the_same_org_id_twice_is_a_real_conflict(
    tmp_path, monkeypatch,
):
    c = client(tmp_path, monkeypatch)
    _new_org(c, "acme")

    _as(OWNER)
    resp = c.post("/api/orgs", json={"org_id": "acme", "name": "Someone else"})
    assert resp.status_code == 409


def test_a_non_member_cannot_read_the_org_at_all(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    org = _new_org(c)

    _as(OUTSIDER)
    resp = c.get(f"/api/orgs/{org}/agents/booker/versions")
    assert resp.status_code == 403


def test_a_viewer_can_read_but_not_create_a_version(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    org = _new_org(c)

    _as(VIEWER)
    read = c.get(f"/api/orgs/{org}/agents/booker/versions")
    assert read.status_code == 200

    write = c.post(f"/api/orgs/{org}/agents/booker/versions", json={
        "instructions": "Book callbacks.", "model": "gemini-3.5-flash-lite",
        "tools": ["book_callback"], "based_on": 0,
    })
    assert write.status_code == 403


def test_an_editor_can_create_a_version(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    org = _new_org(c)

    _as(EDITOR)
    resp = c.post(f"/api/orgs/{org}/agents/booker/versions", json={
        "instructions": "Book callbacks.", "model": "gemini-3.5-flash-lite",
        "tools": ["book_callback"], "based_on": 0,
    })
    assert resp.status_code == 201
    assert resp.json()["version"] == 1


def test_an_editor_cannot_add_a_member(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    org = _new_org(c)

    _as(EDITOR)
    resp = c.post(f"/api/orgs/{org}/members",
                  json={"subject": "auth0|new-1", "role": "viewer"})
    assert resp.status_code == 403


def test_an_unknown_tool_name_is_refused(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    org = _new_org(c)
    _as(EDITOR)
    resp = c.post(f"/api/orgs/{org}/agents/booker/versions", json={
        "instructions": "x", "model": "gemini-3.5-flash-lite",
        "tools": ["delete_everything"], "based_on": 0,
    })
    assert resp.status_code == 422


def test_a_stale_based_on_returns_a_real_conflict(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    org = _new_org(c)
    _as(EDITOR)
    c.post(f"/api/orgs/{org}/agents/booker/versions", json={
        "instructions": "v1", "model": "gemini-3.5-flash-lite",
        "tools": ["book_callback"], "based_on": 0,
    })
    resp = c.post(f"/api/orgs/{org}/agents/booker/versions", json={
        "instructions": "v2 on stale data", "model": "gemini-3.5-flash-lite",
        "tools": ["book_callback"], "based_on": 0,
    })
    assert resp.status_code == 409


def test_getting_an_unknown_version_is_a_real_404(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    org = _new_org(c)
    _as(VIEWER)
    resp = c.get(f"/api/orgs/{org}/agents/booker/versions/5")
    assert resp.status_code == 404


def test_a_new_agent_has_no_deployment(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    org = _new_org(c)
    _as(VIEWER)
    resp = c.get(f"/api/orgs/{org}/agents/booker/deployment")
    assert resp.status_code == 200
    assert resp.json() is None


def test_deploying_an_unknown_version_is_a_real_422(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    org = _new_org(c)
    _as(EDITOR)
    resp = c.post(f"/api/orgs/{org}/agents/booker/deployment",
                  json={"stable_version": 1})
    assert resp.status_code == 422


def test_deploying_a_canary_returns_it_and_becomes_current(
    tmp_path, monkeypatch,
):
    c = client(tmp_path, monkeypatch)
    org = _new_org(c)
    _as(EDITOR)
    c.post(f"/api/orgs/{org}/agents/booker/versions", json={
        "instructions": "v1", "model": "gemini-3.5-flash-lite",
        "tools": ["book_callback"], "based_on": 0,
    })
    c.post(f"/api/orgs/{org}/agents/booker/versions", json={
        "instructions": "v2", "model": "gemini-3.5-flash-lite",
        "tools": ["book_callback", "issue_refund"], "based_on": 1,
    })

    resp = c.post(f"/api/orgs/{org}/agents/booker/deployment", json={
        "stable_version": 1, "canary_version": 2, "canary_percent": 30.0,
    })
    assert resp.status_code == 201
    assert resp.json()["canary_version"] == 2

    _as(VIEWER)
    resp = c.get(f"/api/orgs/{org}/agents/booker/deployment")
    assert resp.json() == {
        "stable_version": 1, "canary_version": 2, "canary_percent": 30.0,
        "created_at": resp.json()["created_at"],
    }


def test_playground_call_refuses_an_agent_with_no_version(
    tmp_path, monkeypatch,
):
    c = client(tmp_path, monkeypatch)
    org = _new_org(c)
    _as(EDITOR)
    resp = c.post(f"/api/orgs/{org}/agents/booker/playground/call", json={
        "question_audio": "audio/ch09/plain.wav",
    })
    assert resp.status_code == 404


def test_a_viewer_cannot_run_a_playground_call(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    org = _new_org(c)
    _as(EDITOR)
    c.post(f"/api/orgs/{org}/agents/booker/versions", json={
        "instructions": "Book callbacks.", "model": "gemini-3.5-flash-lite",
        "tools": ["book_callback"], "based_on": 0,
    })

    _as(VIEWER)
    resp = c.post(f"/api/orgs/{org}/agents/booker/playground/call", json={
        "question_audio": "audio/ch09/plain.wav",
    })
    assert resp.status_code == 403


def test_playground_call_places_a_call_against_the_current_version(
    tmp_path, monkeypatch,
):
    c = client(tmp_path, monkeypatch)
    org = _new_org(c)
    _as(EDITOR)
    c.post(f"/api/orgs/{org}/agents/booker/versions", json={
        "instructions": "Book callbacks.", "model": "gemini-3.5-flash-lite",
        "tools": ["book_callback"], "based_on": 0,
    })

    async def fake_one_call(number, agent, run_dir, question, listen_s=20.0):
        assert agent == "booker"
        assert question == "audio/ch09/plain.wav"
        return {"ok": True, "room": "call-fake", "join_s": 3.0, "ttfa_s": 6.0}

    monkeypatch.setattr(studio_api, "one_call", fake_one_call)

    resp = c.post(f"/api/orgs/{org}/agents/booker/playground/call", json={
        "question_audio": "audio/ch09/plain.wav",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["room"] == "call-fake"
