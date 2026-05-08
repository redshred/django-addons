"""Tests for django_keycloak.conf — settings, URL builders, async HTTP."""

from urllib.parse import parse_qs, urlparse

import pytest
from aioresponses import aioresponses
from django.core.cache import cache
from django.test import override_settings
from django_keycloak import conf


def test_realm_name_reads_settings():
    assert conf.realm_name() == "testrealm"


def test_build_authorization_url_includes_required_params():
    url = conf.build_authorization_url(state="abc123", redirect_uri="https://app/cb", scope="openid profile email")
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "kc.example.com"
    assert parsed.path.endswith("/protocol/openid-connect/auth")
    assert qs["response_type"] == ["code"]
    assert qs["client_id"] == ["testclient"]
    assert qs["redirect_uri"] == ["https://app/cb"]
    assert qs["scope"] == ["openid profile email"]
    assert qs["state"] == ["abc123"]


def test_build_authorization_url_uses_public_url_even_with_internal():
    """The browser-facing URL must always point at the public hostname."""
    with override_settings(KEYCLOAK_SERVER_INTERNAL_URL="http://keycloak:8080"):
        url = conf.build_authorization_url(state="s", redirect_uri="r", scope="openid")
    assert url.startswith("https://kc.example.com/")


def test_server_to_server_headers_empty_when_urls_match():
    assert conf._server_to_server_headers() == {}


def test_server_to_server_headers_set_for_internal_url():
    with override_settings(KEYCLOAK_SERVER_INTERNAL_URL="http://keycloak:8080"):
        headers = conf._server_to_server_headers()
    assert headers == {"Host": "kc.example.com", "X-Forwarded-Proto": "https"}


@pytest.mark.asyncio
async def test_get_well_known_oidc_caches(well_known):
    with aioresponses() as mocked:
        mocked.get(
            "https://kc.example.com/realms/testrealm/.well-known/openid-configuration",
            payload=well_known,
        )
        first = await conf.get_well_known_oidc()
        # Second call must hit cache, not the network. aioresponses only
        # registered one response; a second request would 500/error.
        second = await conf.get_well_known_oidc()

    assert first == well_known
    assert second == well_known
    assert cache.get("django_keycloak:well_known_oidc") == well_known


@pytest.mark.asyncio
async def test_get_certs_fetches_from_jwks_uri(well_known, certs):
    cache.set("django_keycloak:well_known_oidc", well_known, 3600)
    with aioresponses() as mocked:
        mocked.get(well_known["jwks_uri"], payload=certs)
        result = await conf.get_certs()

    assert result == certs
    assert cache.get("django_keycloak:certs") == certs


@pytest.mark.asyncio
async def test_get_issuer_swaps_internal_to_public(well_known):
    well_known = {
        **well_known,
        "issuer": "http://keycloak:8080/realms/testrealm",
    }
    cache.set("django_keycloak:well_known_oidc", well_known, 3600)
    with override_settings(KEYCLOAK_SERVER_INTERNAL_URL="http://keycloak:8080"):
        issuer = await conf.get_issuer()
    assert issuer == "https://kc.example.com/realms/testrealm"


@pytest.mark.asyncio
async def test_exchange_authorization_code_posts_to_token_endpoint(well_known, token_response):
    cache.set("django_keycloak:well_known_oidc", well_known, 3600)
    with aioresponses() as mocked:
        mocked.post(well_known["token_endpoint"], payload=token_response)
        result = await conf.exchange_authorization_code(code="abc", redirect_uri="https://app/cb")
    assert result == token_response


@pytest.mark.asyncio
async def test_refresh_tokens_posts_grant_type(well_known, token_response):
    cache.set("django_keycloak:well_known_oidc", well_known, 3600)
    with aioresponses() as mocked:
        mocked.post(well_known["token_endpoint"], payload=token_response)
        result = await conf.refresh_tokens(refresh_token="r")
    assert result == token_response


@pytest.mark.asyncio
async def test_build_end_session_url_includes_hint_and_redirect(well_known):
    cache.set("django_keycloak:well_known_oidc", well_known, 3600)
    url = await conf.build_end_session_url(
        id_token_hint="abc.def.ghi",
        post_logout_redirect_uri="https://app/done",
    )
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert parsed.path.endswith("/protocol/openid-connect/logout")
    assert qs["client_id"] == ["testclient"]
    assert qs["id_token_hint"] == ["abc.def.ghi"]
    assert qs["post_logout_redirect_uri"] == ["https://app/done"]


@pytest.mark.asyncio
async def test_build_end_session_url_omits_optional_params(well_known):
    cache.set("django_keycloak:well_known_oidc", well_known, 3600)
    url = await conf.build_end_session_url()
    qs = parse_qs(urlparse(url).query)
    assert qs == {"client_id": ["testclient"]}


@pytest.mark.asyncio
async def test_refresh_cache_repopulates(well_known, certs):
    with aioresponses() as mocked:
        mocked.get(
            "https://kc.example.com/realms/testrealm/.well-known/openid-configuration",
            payload=well_known,
        )
        mocked.get(well_known["jwks_uri"], payload=certs)
        await conf.refresh_cache()

    assert cache.get("django_keycloak:well_known_oidc") == well_known
    assert cache.get("django_keycloak:certs") == certs
