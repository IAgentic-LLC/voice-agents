"""Chapter 32: the real HTTP surface the Studio talks to, checked
against a real (temporary) registry file and a mocked live call."""

from fastapi.testclient import TestClient

import studio_api


def client(tmp_path, monkeypatch):
    monkeypatch.setattr(studio_api, "STUDIO_DB", str(tmp_path / "r.db"))
    return TestClient(studio_api.app)


def test_tools_lists_the_real_registered_factories(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    resp = c.get("/api/tools")
    assert resp.status_code == 200
    assert resp.json() == ["book_callback", "issue_refund"]


def test_a_new_agent_has_no_versions(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    resp = c.get("/api/agents/booker/versions")
    assert resp.status_code == 200
    assert resp.json() == []


def test_creating_a_version_returns_it(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    resp = c.post("/api/agents/booker/versions", json={
        "instructions": "Book callbacks.", "model": "gemini-3.5-flash-lite",
        "tools": ["book_callback"], "based_on": 0,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["version"] == 1
    assert body["tools"] == ["book_callback"]


def test_an_unknown_tool_name_is_refused(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    resp = c.post("/api/agents/booker/versions", json={
        "instructions": "x", "model": "gemini-3.5-flash-lite",
        "tools": ["delete_everything"], "based_on": 0,
    })
    assert resp.status_code == 422


def test_a_stale_based_on_returns_a_real_conflict(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    c.post("/api/agents/booker/versions", json={
        "instructions": "v1", "model": "gemini-3.5-flash-lite",
        "tools": ["book_callback"], "based_on": 0,
    })
    resp = c.post("/api/agents/booker/versions", json={
        "instructions": "v2 on stale data", "model": "gemini-3.5-flash-lite",
        "tools": ["book_callback"], "based_on": 0,
    })
    assert resp.status_code == 409


def test_getting_an_unknown_version_is_a_real_404(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    resp = c.get("/api/agents/booker/versions/5")
    assert resp.status_code == 404


def test_a_new_agent_has_no_deployment(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    resp = c.get("/api/agents/booker/deployment")
    assert resp.status_code == 200
    assert resp.json() is None


def test_deploying_an_unknown_version_is_a_real_422(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    resp = c.post("/api/agents/booker/deployment", json={
        "stable_version": 1,
    })
    assert resp.status_code == 422


def test_deploying_a_canary_returns_it_and_becomes_current(
    tmp_path, monkeypatch,
):
    c = client(tmp_path, monkeypatch)
    c.post("/api/agents/booker/versions", json={
        "instructions": "v1", "model": "gemini-3.5-flash-lite",
        "tools": ["book_callback"], "based_on": 0,
    })
    c.post("/api/agents/booker/versions", json={
        "instructions": "v2", "model": "gemini-3.5-flash-lite",
        "tools": ["book_callback", "issue_refund"], "based_on": 1,
    })

    resp = c.post("/api/agents/booker/deployment", json={
        "stable_version": 1, "canary_version": 2, "canary_percent": 30.0,
    })
    assert resp.status_code == 201
    assert resp.json()["canary_version"] == 2

    resp = c.get("/api/agents/booker/deployment")
    assert resp.json() == {
        "stable_version": 1, "canary_version": 2, "canary_percent": 30.0,
        "created_at": resp.json()["created_at"],
    }


def test_playground_call_refuses_an_agent_with_no_version(
    tmp_path, monkeypatch,
):
    c = client(tmp_path, monkeypatch)
    resp = c.post("/api/agents/booker/playground/call", json={
        "question_audio": "audio/ch09/plain.wav",
    })
    assert resp.status_code == 404


def test_playground_call_places_a_call_against_the_current_version(
    tmp_path, monkeypatch,
):
    c = client(tmp_path, monkeypatch)
    c.post("/api/agents/booker/versions", json={
        "instructions": "Book callbacks.", "model": "gemini-3.5-flash-lite",
        "tools": ["book_callback"], "based_on": 0,
    })

    async def fake_one_call(number, agent, run_dir, question, listen_s=20.0):
        assert agent == "booker"
        assert question == "audio/ch09/plain.wav"
        return {"ok": True, "room": "call-fake", "join_s": 3.0, "ttfa_s": 6.0}

    monkeypatch.setattr(studio_api, "one_call", fake_one_call)

    resp = c.post("/api/agents/booker/playground/call", json={
        "question_audio": "audio/ch09/plain.wav",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["room"] == "call-fake"
