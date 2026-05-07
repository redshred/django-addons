import logging
import secrets

from django.conf import settings
from django.contrib.auth import aauthenticate, alogin, alogout
from django.http.response import (
    HttpResponseBadRequest,
    HttpResponseRedirect,
    HttpResponseServerError,
)
from django.shortcuts import resolve_url
from django.urls.base import reverse
from django.views import View

from django_keycloak import conf

logger = logging.getLogger(__name__)


SESSION_STATE_KEY = "oidc_state"
SESSION_NEXT_PATH_KEY = "oidc_next_path"


class Login(View):
    async def get(self, request):
        state = secrets.token_urlsafe(32)
        redirect_uri = request.build_absolute_uri(
            location=reverse("keycloak_login_complete")
        )

        request.session[SESSION_STATE_KEY] = state
        request.session[SESSION_NEXT_PATH_KEY] = request.GET.get("next")

        url = conf.build_authorization_url(
            state=state,
            redirect_uri=redirect_uri,
            # 'openid given_name family_name email' produced "invalid_scope"
            # against newer Keycloak releases; profile + email cover both.
            scope="openid profile email",
        )
        logger.debug("Keycloak authorization URL: %s", url)
        return HttpResponseRedirect(url)


class LoginComplete(View):
    async def get(self, request):
        if "error" in request.GET:
            return HttpResponseServerError(request.GET["error"])

        if "code" not in request.GET or "state" not in request.GET:
            return HttpResponseBadRequest()

        expected_state = request.session.pop(SESSION_STATE_KEY, None)
        next_path = request.session.pop(SESSION_NEXT_PATH_KEY, None)

        if not expected_state or request.GET["state"] != expected_state:
            return HttpResponseRedirect(reverse("keycloak_login"))

        redirect_uri = request.build_absolute_uri(
            location=reverse("keycloak_login_complete")
        )

        user = await aauthenticate(
            request=request,
            code=request.GET["code"],
            redirect_uri=redirect_uri,
        )
        if user is None:
            return HttpResponseRedirect(reverse("keycloak_login"))

        await alogin(request, user)

        if settings.LOGIN_REDIRECT_URL:
            return HttpResponseRedirect(
                resolve_url(settings.LOGIN_REDIRECT_URL)
            )
        return HttpResponseRedirect(next_path or "/")


class Logout(View):
    async def get(self, request):
        profile = getattr(await request.auser(), "oidc_profile", None)
        if profile is not None and profile.refresh_token:
            try:
                await conf.keycloak_logout(refresh_token=profile.refresh_token)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Keycloak logout failed: %s", exc)

            profile.access_token = None
            profile.expires_before = None
            profile.refresh_token = None
            profile.refresh_expires_before = None
            await profile.asave(
                update_fields=[
                    "access_token",
                    "expires_before",
                    "refresh_token",
                    "refresh_expires_before",
                ]
            )

        await alogout(request)

        target = settings.LOGOUT_REDIRECT_URL or reverse("keycloak_login")
        return HttpResponseRedirect(resolve_url(target))
