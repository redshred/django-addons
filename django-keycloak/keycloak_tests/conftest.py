"""Shared fixtures for django-keycloak tests."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

WELL_KNOWN_BASE = "https://kc.example.com/realms/testrealm"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def well_known():
    return {
        "issuer": f"{WELL_KNOWN_BASE}",
        "authorization_endpoint": f"{WELL_KNOWN_BASE}/protocol/openid-connect/auth",
        "token_endpoint": f"{WELL_KNOWN_BASE}/protocol/openid-connect/token",
        "jwks_uri": f"{WELL_KNOWN_BASE}/protocol/openid-connect/certs",
        "userinfo_endpoint": f"{WELL_KNOWN_BASE}/protocol/openid-connect/userinfo",
        "end_session_endpoint": f"{WELL_KNOWN_BASE}/protocol/openid-connect/logout",
        "id_token_signing_alg_values_supported": ["RS256"],
    }


@pytest.fixture
def certs():
    return {"keys": [{"kty": "RSA", "kid": "test-key", "use": "sig", "n": "x", "e": "AQAB"}]}


@pytest.fixture
def primed_cache(well_known, certs):
    """Pre-populate well-known + JWKS caches so HTTP isn't needed."""
    cache.set("django_keycloak:well_known_oidc", well_known, 3600)
    cache.set("django_keycloak:certs", certs, 3600)
    return well_known, certs


@pytest.fixture
def id_token_object():
    """A representative decoded JWT payload."""
    return {
        "sub": "kc-user-1",
        "preferred_username": "alice",
        "email": "alice@example.com",
        "given_name": "Alice",
        "family_name": "Anderson",
        "iss": WELL_KNOWN_BASE,
        "aud": "testclient",
    }


@pytest.fixture
def token_response():
    """Shape of a Keycloak token endpoint response."""
    return {
        "access_token": "access-token-value",
        "refresh_token": "refresh-token-value",
        "id_token": "id-token-value",
        "expires_in": 300,
        "refresh_expires_in": 1800,
        "token_type": "Bearer",
    }


@pytest.fixture
def make_profile(transactional_db, django_user_model):
    """
    Async-safe factory for ``OpenIdConnectProfile`` rows. Returns an awaitable
    so async tests can ``await make_profile(...)`` from inside an event loop
    without tripping ``SynchronousOnlyOperation``.
    """
    from django_keycloak.models import OpenIdConnectProfile

    async def _make(
        *,
        sub="kc-user-1",
        username="alice",
        expired=False,
        refresh_expired=False,
    ):
        user = await django_user_model.objects.acreate(username=username)
        now = timezone.now()
        return await OpenIdConnectProfile.objects.acreate(
            sub=sub,
            user=user,
            access_token="acc",
            refresh_token="ref",
            expires_before=now - timedelta(minutes=1) if expired else now + timedelta(minutes=5),
            refresh_expires_before=now - timedelta(minutes=1) if refresh_expired else now + timedelta(minutes=30),
        )

    return _make
