"""End-to-end tests for the Login / LoginComplete / Logout views."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from django.test import AsyncClient
from django.utils import timezone

from django_keycloak.views import SESSION_NEXT_PATH_KEY, SESSION_STATE_KEY


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_login_view_redirects_to_keycloak_and_stores_state():
    client = AsyncClient()
    response = await client.get("/kc/login?next=/dashboard")

    assert response.status_code == 302
    parsed = urlparse(response["Location"])
    qs = parse_qs(parsed.query)

    assert parsed.netloc == "kc.example.com"
    assert parsed.path.endswith("/protocol/openid-connect/auth")
    assert qs["client_id"] == ["testclient"]
    assert qs["state"]
    state = qs["state"][0]

    assert client.session[SESSION_STATE_KEY] == state
    assert client.session[SESSION_NEXT_PATH_KEY] == "/dashboard"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_login_complete_with_valid_state_logs_in_user(
    primed_cache, id_token_object, token_response
):
    client = AsyncClient()
    # Prime the session with the state the view will compare against.
    session = client.session
    session[SESSION_STATE_KEY] = "expected-state"
    session[SESSION_NEXT_PATH_KEY] = "/dashboard"
    await session.asave()
    client.cookies["sessionid"] = session.session_key

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
        response = await client.get(
            "/kc/login-complete?code=abc&state=expected-state"
        )

    assert response.status_code == 302
    assert response["Location"] == "/dashboard"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_login_complete_with_state_mismatch_redirects_to_login():
    client = AsyncClient()
    session = client.session
    session[SESSION_STATE_KEY] = "expected"
    await session.asave()
    client.cookies["sessionid"] = session.session_key

    response = await client.get(
        "/kc/login-complete?code=abc&state=wrong"
    )
    assert response.status_code == 302
    assert response["Location"].endswith("/kc/login")


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_login_complete_returns_400_when_code_missing():
    client = AsyncClient()
    response = await client.get("/kc/login-complete?state=foo")
    assert response.status_code == 400


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_login_complete_returns_500_on_oauth_error():
    client = AsyncClient()
    response = await client.get(
        "/kc/login-complete?error=invalid_request"
    )
    assert response.status_code == 500


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_logout_view_calls_keycloak_and_clears_tokens(
    make_profile, django_user_model
):
    profile = await make_profile(username="alice")

    client = AsyncClient()
    await client.aforce_login(profile.user)

    logout_mock = AsyncMock()
    with patch("django_keycloak.views.conf.keycloak_logout", logout_mock):
        response = await client.get("/kc/logout")

    assert response.status_code == 302
    logout_mock.assert_awaited_once_with(refresh_token="ref")

    await profile.arefresh_from_db()
    assert profile.access_token is None
    assert profile.refresh_token is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_logout_view_tolerates_keycloak_failure(make_profile):
    profile = await make_profile(username="alice")

    client = AsyncClient()
    await client.aforce_login(profile.user)

    failing_logout = AsyncMock(side_effect=RuntimeError("boom"))
    with patch("django_keycloak.views.conf.keycloak_logout", failing_logout):
        response = await client.get("/kc/logout")

    # The user's local session must still be cleared even if Keycloak errors.
    assert response.status_code == 302
    await profile.arefresh_from_db()
    assert profile.access_token is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_logout_view_with_anonymous_user(django_user_model):
    client = AsyncClient()
    response = await client.get("/kc/logout")
    assert response.status_code == 302
