"""End-to-end tests for the Login / LoginComplete / Logout views."""

from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from django.test import AsyncClient
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
async def test_login_complete_with_valid_state_logs_in_user(primed_cache, id_token_object, token_response):
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
        response = await client.get("/kc/login-complete?code=abc&state=expected-state")

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

    response = await client.get("/kc/login-complete?code=abc&state=wrong")
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
    response = await client.get("/kc/login-complete?error=invalid_request")
    assert response.status_code == 500


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_logout_view_redirects_to_end_session_with_id_token_hint(make_profile, primed_cache):
    profile = await make_profile(username="alice")
    profile.id_token = "stored-id-token"
    await profile.asave(update_fields=["id_token"])

    client = AsyncClient()
    await client.aforce_login(profile.user)

    response = await client.get("/kc/logout")

    assert response.status_code == 302
    location = urlparse(response["Location"])
    assert location.netloc == "kc.example.com"
    assert location.path.endswith("/protocol/openid-connect/logout")

    qs = parse_qs(location.query)
    assert qs["client_id"] == ["testclient"]
    assert qs["id_token_hint"] == ["stored-id-token"]
    assert qs["post_logout_redirect_uri"][0].endswith("/kc/login")

    await profile.arefresh_from_db()
    assert profile.access_token is None
    assert profile.refresh_token is None
    assert profile.id_token is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_logout_view_falls_back_when_well_known_unreachable(
    make_profile,
):
    profile = await make_profile(username="alice")

    client = AsyncClient()
    await client.aforce_login(profile.user)

    failing = AsyncMock(side_effect=RuntimeError("boom"))
    with patch("django_keycloak.views.conf.build_end_session_url", failing):
        response = await client.get("/kc/logout")

    # Local logout should still succeed even if the end-session URL can't
    # be built.
    assert response.status_code == 302
    await profile.arefresh_from_db()
    assert profile.access_token is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_logout_view_with_anonymous_user(primed_cache):
    client = AsyncClient()
    response = await client.get("/kc/logout")
    # Anonymous users still get redirected to Keycloak's end-session URL
    # (with no id_token_hint); idempotent and harmless.
    assert response.status_code == 302
