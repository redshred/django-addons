from __future__ import annotations

from collections.abc import Awaitable, Callable

from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.http import HttpRequest, HttpResponse

from . import generate_request_id
from .conf import REQUEST_ID_HEADER
from .local import reset
from .local import set as _set

GetResponse = Callable[[HttpRequest], HttpResponse | Awaitable[HttpResponse]]


def get_request_id(request: HttpRequest) -> str:
    if hasattr(request, "request_id"):
        return request.request_id
    if REQUEST_ID_HEADER:
        return request.META.get(REQUEST_ID_HEADER, "") or generate_request_id()
    return generate_request_id()


class RequestIdMiddleware:
    sync_capable = True
    async_capable = True

    def __init__(self, get_response: GetResponse) -> None:
        self.get_response = get_response
        self.async_mode = iscoroutinefunction(get_response)
        if self.async_mode:
            markcoroutinefunction(self)

    def __call__(self, request: HttpRequest):
        if self.async_mode:
            return self.__acall__(request)
        token = _set(get_request_id(request))
        try:
            request.request_id = token.var.get()
            return self.get_response(request)
        finally:
            reset(token)

    async def __acall__(self, request: HttpRequest) -> HttpResponse:
        token = _set(get_request_id(request))
        try:
            request.request_id = token.var.get()
            return await self.get_response(request)
        finally:
            reset(token)
