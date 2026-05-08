"""Tests for the bearer-token middleware."""

from unittest.mock import AsyncMock, Mock

import pytest
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from django_keycloak.middleware import (
    KeycloakStatelessBearerAuthenticationMiddleware,
)


def _sync_get_response(_request):
    return HttpResponse("ok")


async def _async_get_response(_request):
    return HttpResponse("ok")


def _request(authorization=None, path="/api/things"):
    rf = RequestFactory()
    headers = {}
    if authorization is not None:
        headers["HTTP_AUTHORIZATION"] = authorization
    return rf.get(path, **headers)


def test_sync_returns_401_without_authorization_header():
    middleware = KeycloakStatelessBearerAuthenticationMiddleware(
        _sync_get_response
    )
    response = middleware(_request())
    assert response.status_code == 401
    assert 'realm="testrealm"' in response["WWW-Authenticate"]


def test_sync_returns_401_for_malformed_header():
    middleware = KeycloakStatelessBearerAuthenticationMiddleware(
        _sync_get_response
    )
    response = middleware(_request(authorization="just-some-string"))
    assert response.status_code == 401


def test_sync_returns_401_for_non_bearer_scheme():
    middleware = KeycloakStatelessBearerAuthenticationMiddleware(
        _sync_get_response
    )
    response = middleware(_request(authorization="Basic abc123"))
    assert response.status_code == 401


def test_sync_returns_401_for_invalid_bearer_token(monkeypatch):
    monkeypatch.setattr(
        "django_keycloak.middleware.authenticate", lambda **kw: None
    )
    middleware = KeycloakStatelessBearerAuthenticationMiddleware(
        _sync_get_response
    )
    response = middleware(_request(authorization="Bearer bad"))
    assert response.status_code == 401


def test_sync_passes_request_through_for_valid_token(monkeypatch):
    fake_user = Mock(is_authenticated=True, username="alice")
    monkeypatch.setattr(
        "django_keycloak.middleware.authenticate",
        lambda **kw: fake_user,
    )
    middleware = KeycloakStatelessBearerAuthenticationMiddleware(
        _sync_get_response
    )
    request = _request(authorization="Bearer good")
    response = middleware(request)
    assert response.status_code == 200
    assert request.user is fake_user


def test_sync_skips_auth_on_exempt_path():
    with override_settings(
        KEYCLOAK_BEARER_AUTHENTICATION_EXEMPT_PATHS=[r"^public/.*"]
    ):
        middleware = KeycloakStatelessBearerAuthenticationMiddleware(
            _sync_get_response
        )
        response = middleware(_request(path="/public/health"))
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_async_returns_401_without_authorization_header():
    middleware = KeycloakStatelessBearerAuthenticationMiddleware(
        _async_get_response
    )
    response = await middleware(_request())
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_async_passes_request_through_for_valid_token(monkeypatch):
    fake_user = Mock(is_authenticated=True, username="alice")
    monkeypatch.setattr(
        "django_keycloak.middleware.aauthenticate",
        AsyncMock(return_value=fake_user),
    )
    middleware = KeycloakStatelessBearerAuthenticationMiddleware(
        _async_get_response
    )
    request = _request(authorization="Bearer good")
    response = await middleware(request)
    assert response.status_code == 200
    assert request.user is fake_user


@pytest.mark.asyncio
async def test_async_returns_401_for_invalid_token(monkeypatch):
    monkeypatch.setattr(
        "django_keycloak.middleware.aauthenticate",
        AsyncMock(return_value=None),
    )
    middleware = KeycloakStatelessBearerAuthenticationMiddleware(
        _async_get_response
    )
    response = await middleware(_request(authorization="Bearer bad"))
    assert response.status_code == 401
