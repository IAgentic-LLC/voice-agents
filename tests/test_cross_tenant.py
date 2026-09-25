"""Chapter 34: zero tolerance. Every one of these requests is a
member of ACME asking for something that belongs to GLOBEX, or the
reverse. Every single one must be refused; there is no case where
a valid token and a real role in the WRONG organization is enough.
"""

import pytest
from fastapi.testclient import TestClient

import studio_api
from voicelab.auth import Principal, verify_token

ACME_OWNER = "auth0|acme-owner"
GLOBEX_OWNER = "auth0|globex-owner"


def _as(subject: str) -> None:
    studio_api.app.dependency_overrides[verify_token] = (
        lambda: Principal(subject=subject)
    )


@pytest.fixture
def two_orgs(tmp_path, monkeypatch):
    monkeypatch.setattr(studio_api, "STUDIO_DB", str(tmp_path / "r.db"))
    studio_api.app.dependency_overrides.clear()
    c = TestClient(studio_api.app)

    _as(ACME_OWNER)
    c.post("/api/orgs", json={"org_id": "acme", "name": "Acme Corp"})
    c.post("/api/orgs/acme/agents/booker/versions", json={
        "instructions": "Acme's own booker.", "model": "gemini-3.5-flash-lite",
        "tools": ["book_callback"], "based_on": 0,
    })
    c.post("/api/orgs/acme/agents/booker/deployment",
          json={"stable_version": 1})

    _as(GLOBEX_OWNER)
    c.post("/api/orgs", json={"org_id": "globex", "name": "Globex Inc"})
    c.post("/api/orgs/globex/agents/booker/versions", json={
        "instructions": "Globex's own booker, a different secret.",
        "model": "gemini-3.5-flash-lite",
        "tools": ["book_callback", "issue_refund"], "based_on": 0,
    })
    c.post("/api/orgs/globex/agents/booker/deployment",
          json={"stable_version": 1})

    return c


CROSS_TENANT_REQUESTS = [
    ("get", "/api/orgs/{org}/agents/booker/versions", None),
    ("get", "/api/orgs/{org}/agents/booker/versions/1", None),
    ("post", "/api/orgs/{org}/agents/booker/versions", {
        "instructions": "smuggled in", "model": "gemini-3.5-flash-lite",
        "tools": ["book_callback"], "based_on": 1,
    }),
    ("get", "/api/orgs/{org}/agents/booker/deployment", None),
    ("post", "/api/orgs/{org}/agents/booker/deployment", {
        "stable_version": 1, "canary_percent": 100.0,
    }),
    ("post", "/api/orgs/{org}/agents/booker/playground/call", {
        "question_audio": "audio/ch09/plain.wav",
    }),
    ("get", "/api/orgs/{org}/members", None),
    ("post", "/api/orgs/{org}/members", {
        "subject": "auth0|intruder", "role": "owner",
    }),
]


@pytest.mark.parametrize("method,path,body", CROSS_TENANT_REQUESTS)
def test_acme_owner_cannot_reach_globex(two_orgs, method, path, body):
    _as(ACME_OWNER)
    resp = two_orgs.request(method.upper(), path.format(org="globex"),
                            json=body)
    assert resp.status_code == 403


@pytest.mark.parametrize("method,path,body", CROSS_TENANT_REQUESTS)
def test_globex_owner_cannot_reach_acme(two_orgs, method, path, body):
    _as(GLOBEX_OWNER)
    resp = two_orgs.request(method.upper(), path.format(org="acme"),
                            json=body)
    assert resp.status_code == 403


def test_each_org_still_reads_its_own_real_data_correctly(two_orgs):
    _as(ACME_OWNER)
    resp = two_orgs.get("/api/orgs/acme/agents/booker/versions/1")
    assert resp.json()["instructions"] == "Acme's own booker."

    _as(GLOBEX_OWNER)
    resp = two_orgs.get("/api/orgs/globex/agents/booker/versions/1")
    assert resp.json()["instructions"] == (
        "Globex's own booker, a different secret."
    )


def test_a_stranger_with_no_membership_anywhere_is_refused_both(two_orgs):
    _as("auth0|nobody-at-all")
    for org in ("acme", "globex"):
        resp = two_orgs.get(f"/api/orgs/{org}/agents/booker/versions")
        assert resp.status_code == 403
