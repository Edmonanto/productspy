"""Supabase JWT verification.

The frontend (src/lib/api.ts) sends the Supabase session access token as
`Authorization: Bearer <jwt>`. We verify it locally with the project's JWT
secret — no network call to Supabase per request.
"""
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str
    name: str
    avatar_url: str | None


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

    if not config.SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_JWT_SECRET is not configured",
        )

    try:
        claims = jwt.decode(
            creds.credentials,
            config.SUPABASE_JWT_SECRET,
            algorithms=[config.JWT_ALGORITHM],
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
