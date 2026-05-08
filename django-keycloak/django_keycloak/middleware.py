import re

from asgiref.sync import iscoroutinefunction
from django.conf import settings
from django.contrib.auth import aauthenticate, authenticate
from django.utils.decorators import sync_and_async_middleware

from django_keycloak import conf
from django_keycloak.response import HttpResponseNotAuthorized


@sync_and_async_middleware
def KeycloakStatelessBearerAuthenticationMiddleware(get_response):
    """
    Validate ``Authorization: Bearer <Keycloak access token>`` on every
    request except those matching ``KEYCLOAK_BEARER_AUTHENTICATION_EXEMPT_PATHS``.
    Sets ``request.user`` to the linked Django user on success; returns 401
    otherwise.
    """

    async_capable = iscoroutinefunction(get_response)

    def _exempt(request) -> bool:
        exempt_paths = getattr(settings, "KEYCLOAK_BEARER_AUTHENTICATION_EXEMPT_PATHS", None)
        if not exempt_paths:
            return False
        path = request.path_info.lstrip("/")
        return any(re.match(m, path) for m in exempt_paths)

    def _extract_token(request) -> str | None:
        header = request.META.get("HTTP_AUTHORIZATION")
        if not header:
            return None
        try:
            scheme, token = header.split(" ", 1)
        except ValueError:
            return None
        if scheme.lower() != "bearer":
            return None
        return token

    def _unauthorized() -> HttpResponseNotAuthorized:
        return HttpResponseNotAuthorized(attributes={"realm": conf.realm_name()})

    if async_capable:

        async def middleware(request):
            if _exempt(request):
                return await get_response(request)

            token = _extract_token(request)
            if token is None:
                return _unauthorized()

            user = await aauthenticate(request=request, access_token=token)
            if user is None:
                return _unauthorized()

            request.user = user
            return await get_response(request)

        return middleware

    def middleware(request):
        if _exempt(request):
            return get_response(request)

        token = _extract_token(request)
        if token is None:
            return _unauthorized()

        user = authenticate(request=request, access_token=token)
        if user is None:
            return _unauthorized()

        request.user = user
        return get_response(request)

    return middleware
