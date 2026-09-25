"""Chapter 34: deterministic JWT verification, the same seam
Book 3's `reorder_app.auth` already proved. A local RSA keypair
stands in for Auth0's own signing key, no live tenant needed here;
`tests/test_auth_live.py` is where the real tenant gets exercised.
"""

import time

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from voicelab import auth
from voicelab.auth import Principal, register_auth_exception_handlers, verify_token

_TEST_AUDIENCE = "https://voice-agent-studio.dev/api"
_TEST_ISSUER = "https://test-tenant.auth0.com/"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _FakeSigningKey:
    def __init__(self, key):
        self.key = key


class _FakeJWKSClient:
    def get_signing_key_from_jwt(self, token: str) -> _FakeSigningKey:
        return _FakeSigningKey(_private_key.public_key())


def _make_token(*, audience=_TEST_AUDIENCE, issuer=_TEST_ISSUER,
                exp_delta=3600, subject="test|123"):
    now = int(time.time())
    payload = {"sub": subject, "aud": audience, "iss": issuer,
              "iat": now, "exp": now + exp_delta}
    return jwt.encode(payload, _private_key, algorithm="RS256")


def _override_jwks(monkeypatch):
    monkeypatch.setattr(auth, "_jwks_client", _FakeJWKSClient())
    monkeypatch.setenv("AUTH0_AUDIENCE", _TEST_AUDIENCE)
    monkeypatch.setenv("AUTH0_DOMAIN", "test-tenant.auth0.com")


def _make_app() -> FastAPI:
    app = FastAPI()
    register_auth_exception_handlers(app)

    @app.get("/whoami")
    def whoami(principal: Principal = Depends(verify_token)) -> dict:
        return {"subject": principal.subject}

    return app


def test_missing_token_is_rejected(monkeypatch):
    _override_jwks(monkeypatch)
    client = TestClient(_make_app())

    response = client.get("/whoami")

    assert response.status_code in (401, 403)


def test_valid_token_is_accepted(monkeypatch):
    _override_jwks(monkeypatch)
    client = TestClient(_make_app())
    token = _make_token(subject="auth0|abc123")

    response = client.get("/whoami",
                          headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"subject": "auth0|abc123"}


def test_expired_token_is_rejected(monkeypatch):
    _override_jwks(monkeypatch)
    client = TestClient(_make_app())
    token = _make_token(exp_delta=-3600)

    response = client.get("/whoami",
                          headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert "detail" in response.json()


def test_wrong_audience_is_rejected(monkeypatch):
    _override_jwks(monkeypatch)
    client = TestClient(_make_app())
    token = _make_token(audience="https://someone-elses-api.dev")

    response = client.get("/whoami",
                          headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
