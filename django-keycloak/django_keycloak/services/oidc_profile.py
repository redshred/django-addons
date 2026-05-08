"""Async OIDC profile management: token exchange, refresh, user upsert."""

import logging
from datetime import timedelta

from django.apps import apps as django_apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from django_keycloak import conf
from django_keycloak.services.exceptions import TokensExpired

logger = logging.getLogger(__name__)


def get_openid_connect_profile_model():
    try:
        return django_apps.get_model(settings.KEYCLOAK_OIDC_PROFILE_MODEL, require_ready=False)
    except ValueError as exc:
        raise ImproperlyConfigured("KEYCLOAK_OIDC_PROFILE_MODEL must be of the form 'app_label.model_name'") from exc
    except LookupError as exc:
        raise ImproperlyConfigured(
            f"KEYCLOAK_OIDC_PROFILE_MODEL refers to model "
            f"'{settings.KEYCLOAK_OIDC_PROFILE_MODEL}' that has not been installed"
        ) from exc


async def update_or_create_from_code(*, code: str, redirect_uri: str) -> "OpenIdConnectProfile":  # noqa: F821
    """Exchange an authorization code for tokens and link to a Django user."""
    initiate_time = timezone.now()
    token_response = await conf.exchange_authorization_code(code=code, redirect_uri=redirect_uri)
    return await _update_or_create(token_response=token_response, initiate_time=initiate_time)


async def get_or_create_from_id_token(*, id_token: str) -> "OpenIdConnectProfile":  # noqa: F821
    """Validate a bearer access/id token and link to a Django user."""
    certs = await conf.get_certs()
    well_known = await conf.get_well_known_oidc()
    issuer = await conf.get_issuer()

    id_token_object = conf.decode_token(id_token, certs=certs, well_known=well_known, issuer=issuer)
    return await _update_or_create_user_and_oidc_profile(id_token_object)


async def _update_or_create(*, token_response: dict, initiate_time):
    certs = await conf.get_certs()
    well_known = await conf.get_well_known_oidc()
    issuer = await conf.get_issuer()

    token_key = "id_token" if "id_token" in token_response else "access_token"
    token_object = conf.decode_token(
        token_response[token_key],
        certs=certs,
        well_known=well_known,
        issuer=issuer,
        # https://github.com/Peter-Slump/django-keycloak/issues/57
        access_token=token_response["access_token"],
    )

    oidc_profile = await _update_or_create_user_and_oidc_profile(token_object)
    return await _update_tokens(oidc_profile, token_response=token_response, initiate_time=initiate_time)


async def _update_or_create_user_and_oidc_profile(id_token_object: dict):
    """
    Upsert (User, OpenIdConnectProfile). Not atomic: a failure between the
    two writes leaves a User without a profile, which the next login fixes.
    Wrapping ``transaction.atomic`` in async requires sync_to_async, which
    would defeat the point of going async; we accept the trade.
    """
    OpenIdConnectProfileModel = get_openid_connect_profile_model()
    UserModel = get_user_model()
    email_field = UserModel.get_email_field_name()

    user, _ = await UserModel.objects.aupdate_or_create(
        username=id_token_object["preferred_username"],
        defaults={
            email_field: id_token_object.get("email", ""),
            "first_name": id_token_object.get("given_name", ""),
            "last_name": id_token_object.get("family_name", ""),
        },
    )
    oidc_profile, _ = await OpenIdConnectProfileModel.objects.aupdate_or_create(
        sub=id_token_object["sub"], defaults={"user": user}
    )
    return oidc_profile


async def _update_tokens(token_model, *, token_response: dict, initiate_time):
    expires_before = initiate_time + timedelta(seconds=token_response["expires_in"])
    refresh_expires_before = initiate_time + timedelta(seconds=token_response["refresh_expires_in"])

    token_model.access_token = token_response["access_token"]
    token_model.expires_before = expires_before
    token_model.refresh_token = token_response.get("refresh_token")
    token_model.refresh_expires_before = refresh_expires_before

    update_fields = [
        "access_token",
        "expires_before",
        "refresh_token",
        "refresh_expires_before",
    ]
    # Refresh-token grants don't return a new id_token; keep the one from
    # initial login so logout can still pass it as id_token_hint.
    if "id_token" in token_response:
        token_model.id_token = token_response["id_token"]
        update_fields.append("id_token")

    await token_model.asave(update_fields=update_fields)
    return token_model


async def get_active_access_token(oidc_profile) -> str:
    """Return the access token, refreshing via the refresh token if needed."""
    initiate_time = timezone.now()

    if oidc_profile.refresh_expires_before is None or initiate_time > oidc_profile.refresh_expires_before:
        raise TokensExpired()

    if initiate_time > oidc_profile.expires_before:
        token_response = await conf.refresh_tokens(refresh_token=oidc_profile.refresh_token)
        oidc_profile = await _update_tokens(
            oidc_profile,
            token_response=token_response,
            initiate_time=initiate_time,
        )

    return oidc_profile.access_token
