"""Supabase JWT verification.

The frontend (src/lib/api.ts) sends the Supabase session access token as
`Authorization: Bearer <jwt>`.

Supabase signs those tokens with an asymmetric key (ES256 by default now),
publishing the public half at the project's JWKS endpoint. Older projects
still sign HS256 with the shared JWT secret. Both are verified here; the
token's own `alg` header selects the path, and anything else is refused
rather than guessed at.

Public keys are cached by PyJWKClient, so the JWKS endpoint is hit on a cold
start and on key rotation, not per request.
"""
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config

_bearer = HTTPBearer(auto_error=False)

# Built lazily so importing this module never reaches the network.
_jwks_client: jwt.PyJWKClient | None = None


def _jwks() -> jwt.PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(config.SUPABASE_JWKS_URL, cache_keys=True)
    return _jwks_client


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str
    name: str
    avatar_url: str | None


def _misconfigured(detail: str) -> HTTPException:
    """Our configuration is wrong — never blame the caller's token for it."""
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
    )


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """FastAPI dependency: resolve the caller from their Supabase JWT."""
    if creds is None or not creds.credentials:
        raise _unauthorized("Missing authentication token")

    token = creds.credentials
    try:
        alg = jwt.get_unverified_header(token).get("alg")
    except jwt.InvalidTokenError:
        raise _unauthorized("Invalid authentication token")

    if alg in config.ASYMMETRIC_ALGORITHMS:
        if not config.SUPABASE_JWKS_URL:
            raise _misconfigured(
                "SUPABASE_URL is not configured; cannot verify an "
                f"{alg}-signed Supabase token"
            )
        try:
            # Blocking HTTP on a cache miss, so keep it off the event loop.
            key = (await run_in_threadpool(_jwks().get_signing_key_from_jwt, token)).key
        except jwt.PyJWKClientError as exc:
            # Our key source failed, not the caller's token. Saying 401 here
            # would send a valid user to the login page over our own outage.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Cannot reach the Supabase signing keys: {exc}",
            )
    elif alg == config.JWT_ALGORITHM:
        if not config.SUPABASE_JWT_SECRET:
            raise _misconfigured("SUPABASE_JWT_SECRET is not configured")
        key = config.SUPABASE_JWT_SECRET
    else:
        # Never let the token choose an algorithm we did not plan for.
        raise _unauthorized(f"Unsupported token algorithm: {alg}")

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience=config.JWT_AUDIENCE,
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Token has expired")
    except jwt.InvalidTokenError:
        raise _unauthorized("Invalid authentication token")

    user_id = claims.get("sub")
    if not user_id:
        raise _unauthorized("Token is missing a subject claim")

    metadata = claims.get("user_metadata") or {}
    email = claims.get("email") or metadata.get("email") or ""

    return CurrentUser(
        id=user_id,
        email=email,
        name=metadata.get("full_name") or metadata.get("name") or email.split("@")[0],
        avatar_url=metadata.get("avatar_url"),
    )
