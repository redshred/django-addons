"""Tests for django_keycloak.auth.backends."""

from unittest.mock import AsyncMock, patch

import pytest
from django_keycloak.auth.backends import (
    KeycloakAuthorizationCodeBackend,
    KeycloakIDTokenAuthorizationBackend,
)
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_authorization_code_backend_returns_user(primed_cache, id_token_object, token_response):
    backend = KeycloakAuthorizationCodeBackend()
    with (
        patch(
            "django_keycloak.services.oidc_profile.conf.exchange_authorization_code",
            AsyncMock(return_value=token_response),
        ),
        patch(
            "django_keycloak.services.oidc_profile.conf.decode_token",
            return_value=id_token_object,
        ),
    ):
        user = await backend.aauthenticate(request=None, code="abc", redirect_uri="https://app/cb")

    assert user is not None
    assert user.username == "alice"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_authorization_code_backend_returns_none_without_code():
    backend = KeycloakAuthorizationCodeBackend()
    user = await backend.aauthenticate(request=None, code=None, redirect_uri=None)
    assert user is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_id_token_backend_returns_user(primed_cache, id_token_object):
    backend = KeycloakIDTokenAuthorizationBackend()
    with patch(
        "django_keycloak.services.oidc_profile.conf.decode_token",
        return_value=id_token_object,
    ):
        user = await backend.aauthenticate(request=None, access_token="raw-jwt")

    assert user is not None
    assert user.username == "alice"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        ExpiredSignatureError("expired"),
        JWTClaimsError("bad claim"),
        JWTError("malformed"),
    ],
)
async def test_id_token_backend_swallows_jwt_errors(primed_cache, exc):
    backend = KeycloakIDTokenAuthorizationBackend()
    with patch(
        "django_keycloak.services.oidc_profile.conf.decode_token",
        side_effect=exc,
    ):
        user = await backend.aauthenticate(request=None, access_token="bad")
    assert user is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_aget_user_returns_user_when_refresh_valid(make_profile):
    profile = await make_profile()
    backend = KeycloakAuthorizationCodeBackend()
    user = await backend.aget_user(profile.user_id)
    assert user is not None
    assert user.pk == profile.user_id


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_aget_user_returns_none_when_refresh_expired(make_profile):
    profile = await make_profile(refresh_expired=True)
    backend = KeycloakAuthorizationCodeBackend()
    user = await backend.aget_user(profile.user_id)
    assert user is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_aget_user_returns_none_when_user_missing():
    backend = KeycloakAuthorizationCodeBackend()
    user = await backend.aget_user(99999)
    assert user is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_aget_user_returns_none_when_no_profile(django_user_model):
    user = await django_user_model.objects.acreate(username="orphan")
    backend = KeycloakAuthorizationCodeBackend()
    assert await backend.aget_user(user.pk) is None


def test_get_all_permissions_is_noop():
    backend = KeycloakAuthorizationCodeBackend()
    assert backend.get_all_permissions(user_obj=None) == set()


def test_has_perm_is_noop():
    backend = KeycloakAuthorizationCodeBackend()
    assert backend.has_perm(user_obj=None, perm="any.perm") is False


@pytest.mark.django_db(transaction=True)
def test_sync_authenticate_wrapper(primed_cache, id_token_object, token_response):
    """The sync authenticate() wrapper must round-trip through aauthenticate."""
    backend = KeycloakAuthorizationCodeBackend()
    with (
        patch(
            "django_keycloak.services.oidc_profile.conf.exchange_authorization_code",
            AsyncMock(return_value=token_response),
        ),
        patch(
            "django_keycloak.services.oidc_profile.conf.decode_token",
            return_value=id_token_object,
        ),
    ):
        user = backend.authenticate(request=None, code="abc", redirect_uri="https://app/cb")
    assert user is not None
    assert user.username == "alice"
