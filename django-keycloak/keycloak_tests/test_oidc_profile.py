"""Tests for django_keycloak.services.oidc_profile."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_keycloak.models import OpenIdConnectProfile
from django_keycloak.services import oidc_profile as svc
from django_keycloak.services.exceptions import TokensExpired


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_update_or_create_from_code_creates_user_and_profile(primed_cache, id_token_object, token_response):
    with (
        patch.object(
            svc.conf,
            "exchange_authorization_code",
            AsyncMock(return_value=token_response),
        ),
        patch.object(svc.conf, "decode_token", return_value=id_token_object),
    ):
        profile = await svc.update_or_create_from_code(code="abc", redirect_uri="https://app/cb")

    assert profile.sub == "kc-user-1"
    assert profile.access_token == token_response["access_token"]
    assert profile.refresh_token == token_response["refresh_token"]
    assert profile.expires_before > timezone.now()
    assert profile.user.username == "alice"
    assert profile.user.email == "alice@example.com"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_update_or_create_from_code_updates_existing_user(primed_cache, id_token_object, token_response):
    User = get_user_model()
    await User.objects.acreate(username="alice", first_name="OldName")

    with (
        patch.object(
            svc.conf,
            "exchange_authorization_code",
            AsyncMock(return_value=token_response),
        ),
        patch.object(svc.conf, "decode_token", return_value=id_token_object),
    ):
        profile = await svc.update_or_create_from_code(code="abc", redirect_uri="https://app/cb")

    await profile.user.arefresh_from_db()
    assert profile.user.first_name == "Alice"
    assert await User.objects.acount() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_get_or_create_from_id_token_decodes_and_links(primed_cache, id_token_object):
    with patch.object(svc.conf, "decode_token", return_value=id_token_object) as decode_mock:
        profile = await svc.get_or_create_from_id_token(id_token="raw-jwt")

    assert profile.sub == "kc-user-1"
    decode_mock.assert_called_once()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_get_active_access_token_returns_existing_when_valid(make_profile):
    profile = await make_profile()
    token = await svc.get_active_access_token(profile)
    assert token == "acc"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_get_active_access_token_refreshes_when_expired(make_profile, token_response):
    profile = await make_profile(expired=True)

    refreshed = {**token_response, "access_token": "new-access"}
    with patch.object(svc.conf, "refresh_tokens", AsyncMock(return_value=refreshed)) as refresh:
        token = await svc.get_active_access_token(profile)

    refresh.assert_awaited_once_with(refresh_token="ref")
    assert token == "new-access"
    await profile.arefresh_from_db()
    assert profile.access_token == "new-access"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_get_active_access_token_raises_when_refresh_expired(make_profile):
    profile = await make_profile(refresh_expired=True)
    with pytest.raises(TokensExpired):
        await svc.get_active_access_token(profile)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_get_active_access_token_raises_when_no_refresh(make_profile):
    profile = await make_profile()
    profile.refresh_expires_before = None
    await profile.asave(update_fields=["refresh_expires_before"])

    with pytest.raises(TokensExpired):
        await svc.get_active_access_token(profile)


def test_oidc_profile_is_active_property():
    profile = OpenIdConnectProfile(
        access_token="acc",
        expires_before=timezone.now() + timedelta(minutes=5),
    )
    assert profile.is_active is True


def test_oidc_profile_is_active_false_when_expired():
    profile = OpenIdConnectProfile(
        access_token="acc",
        expires_before=timezone.now() - timedelta(minutes=1),
    )
    assert profile.is_active is False


def test_oidc_profile_is_active_false_when_no_token():
    profile = OpenIdConnectProfile(
        access_token=None,
        expires_before=timezone.now() + timedelta(minutes=5),
    )
    assert profile.is_active is False
