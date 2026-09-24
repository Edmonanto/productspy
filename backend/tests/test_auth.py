"""Supabase JWT verification, both signing schemes.

Supabase moved to asymmetric signing keys: tokens arrive as ES256 with a
`kid`, and the public half is published at the project's JWKS endpoint. The
backend verified HS256 against the shared secret only, so every real token
was rejected with 401 and the dashboard rendered empty while the API, the
database and the data were all fine.
"""
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

from app import auth, config
from app.auth import CurrentUser, current_user
from fastapi.security import HTTPAuthorizationCredentials

KID = "6c89d965-fac9-4d02-8ce0-7fc1f3a6cb0d"
SECRET = "legacy-shared-secret"


def claims(**over):
    base = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "aud": config.JWT_AUDIENCE,
        "role": "authenticated",
        "email": "e@x.com",
        "exp": int(time.time()) + 3600,
        "user_metadata": {"full_name": "Edmond"},
    }
    base.update(over)
    return base


@pytest.fixture
def ec_key():
    return ec.generate_private_key(ec.SECP256R1())


def es256(key, **over) -> str:
    return jwt.encode(claims(**over), key, algorithm="ES256",
                      headers={"kid": KID})


def creds(token):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture
def jwks(monkeypatch, ec_key):
    """Stand in for the project's JWKS endpoint — no network in tests."""
    class FakeKey:
        key = ec_key.public_key()

    class FakeClient:
        def get_signing_key_from_jwt(self, token):
            if jwt.get_unverified_header(token).get("kid") != KID:
                raise jwt.PyJWKClientError("no matching key")
            return FakeKey()

    monkeypatch.setattr(auth, "_jwks", lambda: FakeClient())
    monkeypatch.setattr(config, "SUPABASE_JWKS_URL",
                        "https://p.supabase.co/auth/v1/.well-known/jwks.json")


# ── the bug ─────────────────────────────────────────────────────────────────
async def test_es256_token_is_accepted(jwks, ec_key):
    user = await current_user(creds(es256(ec_key)))
    assert isinstance(user, CurrentUser)
    assert user.email == "e@x.com"
    assert user.name == "Edmond"


async def test_hs256_still_works_for_unrotated_projects(monkeypatch):
    monkeypatch.setattr(config, "SUPABASE_JWT_SECRET", SECRET)
    token = jwt.encode(claims(), SECRET, algorithm="HS256")
    assert (await current_user(creds(token))).id == claims()["sub"]


# ── refusals ────────────────────────────────────────────────────────────────
async def test_unknown_kid_is_rejected_as_unavailable_not_invalid(jwks, ec_key):
    """A key we cannot resolve is our problem; 401 would bounce a valid user
    to the login page over our own outage."""
    token = jwt.encode(claims(), ec_key, algorithm="ES256",
                       headers={"kid": "not-our-key"})
    with pytest.raises(HTTPException) as e:
        await current_user(creds(token))
    assert e.value.status_code == 503


async def test_token_signed_by_the_wrong_key_is_rejected(jwks):
    impostor = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(HTTPException) as e:
        await current_user(creds(es256(impostor)))
    assert e.value.status_code == 401


async def test_expired_token_is_rejected(jwks, ec_key):
    with pytest.raises(HTTPException) as e:
        await current_user(creds(es256(ec_key, exp=int(time.time()) - 10)))
    assert e.value.status_code == 401
    assert "expired" in e.value.detail.lower()


async def test_wrong_audience_is_rejected(jwks, ec_key):
    with pytest.raises(HTTPException) as e:
        await current_user(creds(es256(ec_key, aud="anon")))
    assert e.value.status_code == 401


async def test_algorithm_none_is_refused(jwks):
    """The token must never choose an algorithm we did not plan for."""
    token = jwt.encode(claims(), None, algorithm="none")
    with pytest.raises(HTTPException) as e:
        await current_user(creds(token))
    assert e.value.status_code == 401
    assert "Unsupported token algorithm" in e.value.detail


async def test_missing_token_is_rejected():
    with pytest.raises(HTTPException) as e:
        await current_user(None)
    assert e.value.status_code == 401


async def test_missing_jwks_config_is_a_server_error_not_a_401(monkeypatch, ec_key):
    """An unconfigured backend must not look like a bad password to the user."""
    monkeypatch.setattr(config, "SUPABASE_JWKS_URL", "")
    with pytest.raises(HTTPException) as e:
        await current_user(creds(es256(ec_key)))
    assert e.value.status_code == 500
