"""Chapter 34: who is actually calling the Studio API, verified
against a real Auth0 tenant, the same JWT-bearer pattern Book 3's
`reorder_app.auth` already proved. No session, no cookie, no
password stored anywhere in this repo; identity is exactly what a
signed token proves.
"""

import os

import jwt
from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel


def _auth0_domain() -> str:
    return os.environ.get("AUTH0_DOMAIN", "")


def _auth0_audience() -> str:
    return os.environ.get("AUTH0_AUDIENCE", "")


_bearer_scheme = HTTPBearer()
_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(
            f"https://{_auth0_domain()}/.well-known/jwks.json"
        )
    return _jwks_client


class Principal(BaseModel):
    """What a verified token proves: a subject identifier, nothing
    more. Chapter 34's tenant/role tables are keyed by this string,
    Auth0's own opaque `sub` claim."""

    subject: str


class UnauthorizedError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> Principal:
    """Override `_get_jwks_client` (module-level) or this whole
    dependency in a test for a deterministic double, instead of
    calling a live Auth0 tenant on every test run."""
    token = credentials.credentials
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=_auth0_audience(),
            issuer=f"https://{_auth0_domain()}/",
            leeway=30,
        )
    except jwt.PyJWTError as exc:
        raise UnauthorizedError(detail=str(exc)) from exc
    return Principal(subject=payload["sub"])


def register_auth_exception_handlers(app) -> None:
    @app.exception_handler(UnauthorizedError)
    async def handle_unauthorized(request: Request, exc: UnauthorizedError
                                  ) -> JSONResponse:
        return JSONResponse(
            status_code=401, content={"detail": exc.detail},
            headers={"WWW-Authenticate": "Bearer"},
        )
