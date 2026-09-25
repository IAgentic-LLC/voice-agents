"""Chapter 34, contract tier: a real, controlled call to the actual
live Auth0 tenant, fetching a real token via the client-credentials
flow and verifying `voicelab.auth.verify_token` accepts it for real.
Requires AUTH0_DOMAIN, AUTH0_AUDIENCE, AUTH0_TEST_CLIENT_ID,
AUTH0_TEST_CLIENT_SECRET in the environment (see .env), skipped
otherwise rather than failing CI runs that don't have a tenant
configured.
"""

import os

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from voicelab import config  # noqa: F401  (loads .env as a side effect)
from voicelab.auth import Principal, register_auth_exception_handlers, verify_token

pytestmark = pytest.mark.skipif(
    not os.environ.get("AUTH0_TEST_CLIENT_SECRET"),
    reason="No live Auth0 tenant configured for this environment",
)


def test_real_token_from_live_tenant_is_accepted():
    token_response = httpx.post(
        f"https://{os.environ['AUTH0_DOMAIN']}/oauth/token",
        json={
            "client_id": os.environ["AUTH0_TEST_CLIENT_ID"],
            "client_secret": os.environ["AUTH0_TEST_CLIENT_SECRET"],
            "audience": os.environ["AUTH0_AUDIENCE"],
            "grant_type": "client_credentials",
        },
        timeout=10,
    )
    token_response.raise_for_status()
    access_token = token_response.json()["access_token"]

    app = FastAPI()
    register_auth_exception_handlers(app)

    @app.get("/whoami")
    def whoami(principal: Principal = Depends(verify_token)) -> dict:
        return {"subject": principal.subject}

    client = TestClient(app)
    response = client.get("/whoami",
                          headers={"Authorization": f"Bearer {access_token}"})

    assert response.status_code == 200
    assert response.json()["subject"]
