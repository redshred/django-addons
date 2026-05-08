"""
Settings-backed Keycloak configuration + async OIDC primitives.

Replaces the upstream ``Server`` / ``Realm`` / ``Client`` model trio: static
config lives in Django settings, while JWKS and ``.well-known/openid-configuration``
are cached in the Django cache framework. All HTTP traffic to Keycloak goes
through ``aiohttp``; JWT validation stays synchronous (it's a CPU-bound
operation against locally cached keys).

Required settings:
    KEYCLOAK_SERVER_URL         Public-facing Keycloak base URL.
    KEYCLOAK_REALM              Realm name on the Keycloak server.
    KEYCLOAK_CLIENT_ID          OAuth client id.
    KEYCLOAK_CLIENT_SECRET      OAuth client secret.

Optional settings:
    KEYCLOAK_SERVER_INTERNAL_URL  URL used for server-to-server calls when it
                                  differs from the public URL.
    KEYCLOAK_CACHE_TIMEOUT        Seconds to cache JWKS / well-known config.
                                  Defaults to one hour.
"""

from urllib.parse import urlencode, urlparse

import aiohttp
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from jose import jwt

_WELL_KNOWN_CACHE_KEY = "django_keycloak:well_known_oidc"
_CERTS_CACHE_KEY = "django_keycloak:certs"


def _public_url() -> str:
    return settings.KEYCLOAK_SERVER_URL.rstrip("/")


def _internal_url() -> str:
    url = getattr(settings, "KEYCLOAK_SERVER_INTERNAL_URL", None)
    return (url or _public_url()).rstrip("/")


def _cache_timeout() -> int:
    return getattr(settings, "KEYCLOAK_CACHE_TIMEOUT", 60 * 60)


def realm_name() -> str:
    return settings.KEYCLOAK_REALM


def _server_to_server_headers() -> dict[str, str]:
    """
    When server-to-server traffic goes to a different host than the public
    URL, set Host / X-Forwarded-Proto so Keycloak builds issuer URLs and
    redirects against the public hostname.
    """
    public = _public_url()
    internal = _internal_url()
    if internal == public:
        return {}
    parsed = urlparse(public)
    headers = {"Host": parsed.netloc}
    if parsed.scheme == "https":
        headers["X-Forwarded-Proto"] = "https"
    return headers


def _realm_url(internal: bool = True) -> str:
    base = _internal_url() if internal else _public_url()
    return f"{base}/realms/{realm_name()}"


async def get_well_known_oidc() -> dict:
    cached = await sync_to_async(cache.get)(_WELL_KNOWN_CACHE_KEY)
    if cached is not None:
        return cached

    url = f"{_realm_url()}/.well-known/openid-configuration"
    async with aiohttp.ClientSession() as session, session.get(url, headers=_server_to_server_headers()) as resp:
        resp.raise_for_status()
        well_known = await resp.json()

    await sync_to_async(cache.set)(_WELL_KNOWN_CACHE_KEY, well_known, _cache_timeout())
    return well_known


async def get_certs() -> dict:
    cached = await sync_to_async(cache.get)(_CERTS_CACHE_KEY)
    if cached is not None:
        return cached

    well_known = await get_well_known_oidc()
    async with (
        aiohttp.ClientSession() as session,
        session.get(well_known["jwks_uri"], headers=_server_to_server_headers()) as resp,
    ):
        resp.raise_for_status()
        certs = await resp.json()

    await sync_to_async(cache.set)(_CERTS_CACHE_KEY, certs, _cache_timeout())
    return certs


async def get_issuer() -> str:
    """Issuer URL normalized to the public hostname for JWT validation."""
    issuer = (await get_well_known_oidc())["issuer"]
    public = _public_url()
    internal = _internal_url()
    if internal != public:
        return issuer.replace(internal, public, 1)
    return issuer


def build_authorization_url(*, state: str, redirect_uri: str, scope: str) -> str:
    """
    Construct the public-facing Keycloak authorization URL. URL building only
    — no HTTP. The caller is responsible for redirecting the browser.
    """
    params = {
        "response_type": "code",
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
    }
    return f"{_realm_url(internal=False)}/protocol/openid-connect/auth?{urlencode(params)}"


async def _post_token(data: dict) -> dict:
    well_known = await get_well_known_oidc()
    payload = {
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
        **data,
    }
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            well_known["token_endpoint"],
            data=payload,
            headers=_server_to_server_headers(),
        ) as resp,
    ):
        resp.raise_for_status()
        return await resp.json()


async def exchange_authorization_code(*, code: str, redirect_uri: str) -> dict:
    return await _post_token(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
    )


async def refresh_tokens(*, refresh_token: str) -> dict:
    return await _post_token({"grant_type": "refresh_token", "refresh_token": refresh_token})


async def build_end_session_url(
    *,
    id_token_hint: str | None = None,
    post_logout_redirect_uri: str | None = None,
) -> str:
    """
    Build the RP-initiated logout URL for browser redirection.

    Per OIDC RP-Initiated Logout 1.0, the relying party redirects the user's
    browser to ``end_session_endpoint`` with ``id_token_hint`` and
    ``post_logout_redirect_uri``. Keycloak validates the id_token's signature
    (it does not need to be unexpired), terminates the SSO session, and
    redirects the browser back to ``post_logout_redirect_uri`` — which must
    be registered on the Keycloak client as a valid post-logout redirect URI.

    Replaces the deprecated server-side POST to ``end_session_endpoint`` with
    ``refresh_token`` (Keycloak >= 18).
    """
    well_known = await get_well_known_oidc()
    params: dict[str, str] = {"client_id": settings.KEYCLOAK_CLIENT_ID}
    if id_token_hint:
        params["id_token_hint"] = id_token_hint
    if post_logout_redirect_uri:
        params["post_logout_redirect_uri"] = post_logout_redirect_uri
    return f"{well_known['end_session_endpoint']}?{urlencode(params)}"


def decode_token(
    token: str,
    *,
    certs: dict,
    well_known: dict,
    issuer: str,
    access_token: str | None = None,
) -> dict:
    """Local JWT validation against cached JWKS. Synchronous; no HTTP."""
    return jwt.decode(
        token,
        key=certs,
        algorithms=well_known["id_token_signing_alg_values_supported"],
        issuer=issuer,
        access_token=access_token,
        options={"verify_aud": False},
    )


async def refresh_cache() -> None:
    """Drop and repopulate the well-known + JWKS caches."""
    await sync_to_async(cache.delete_many)([_WELL_KNOWN_CACHE_KEY, _CERTS_CACHE_KEY])
    await get_well_known_oidc()
    await get_certs()
