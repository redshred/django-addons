import logging

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.utils import timezone
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError

from django_keycloak.services import oidc_profile as oidc_profile_service

logger = logging.getLogger(__name__)


class KeycloakAuthorizationBase:
    """
    Common ``get_user`` / permission hooks. Both ``aget_user`` (async) and
    ``get_user`` (sync wrapper) are provided so the backend works with
    Django's sync auth helpers as well as async views.
    """

    async def aget_user(self, user_id):
        UserModel = get_user_model()
        try:
            user = await UserModel.objects.select_related("oidc_profile").aget(pk=user_id)
        except UserModel.DoesNotExist:
            return None

        profile = getattr(user, "oidc_profile", None)
        if profile is None or profile.refresh_expires_before is None:
            return None
        if profile.refresh_expires_before > timezone.now():
            return user
        return None

    def get_user(self, user_id):
        return async_to_sync(self.aget_user)(user_id)

    def get_all_permissions(self, user_obj, obj=None):
        return set()

    def has_perm(self, user_obj, perm, obj=None):
        return False


class KeycloakAuthorizationCodeBackend(KeycloakAuthorizationBase):
    """Authenticate against Keycloak via the OAuth2 authorization-code flow."""

    async def aauthenticate(self, request, code=None, redirect_uri=None):
        if code is None or redirect_uri is None:
            return None
        oidc_profile = await oidc_profile_service.update_or_create_from_code(code=code, redirect_uri=redirect_uri)
        return oidc_profile.user

    def authenticate(self, request, code=None, redirect_uri=None):
        return async_to_sync(self.aauthenticate)(request, code=code, redirect_uri=redirect_uri)


class KeycloakIDTokenAuthorizationBackend(KeycloakAuthorizationBase):
    """Authenticate a request bearing a Keycloak access token."""

    async def aauthenticate(self, request, access_token=None):
        if access_token is None:
            return None
        try:
            oidc_profile = await oidc_profile_service.get_or_create_from_id_token(id_token=access_token)
        except ExpiredSignatureError:
            logger.debug("Bearer auth: access token expired.")
            return None
        except JWTClaimsError as exc:
            logger.debug("Bearer auth: claim check failed: %s", exc)
            return None
        except JWTError:
            logger.debug("Bearer auth: malformed access token.")
            return None
        return oidc_profile.user

    def authenticate(self, request, access_token=None):
        return async_to_sync(self.aauthenticate)(request, access_token=access_token)
