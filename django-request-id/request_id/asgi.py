"""
ASGI counterpart to ``request_id.wsgi``: ensures every inbound HTTP/WS scope
carries an ``X-Request-ID`` header, generating one when the upstream server
hasn't already.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from . import generate_request_id

ASGIApp = Callable[[dict[str, Any], Callable[[], Awaitable[Any]], Callable[[Any], Awaitable[None]]], Awaitable[None]]

HEADER_NAME = b"x-request-id"


class AddRequestIdHeaderMiddleware:
    """ASGI middleware that injects ``X-Request-ID`` if the scope lacks one."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            headers = list(scope.get("headers", []))
            if not any(name == HEADER_NAME for name, _ in headers):
                headers.append((HEADER_NAME, generate_request_id().encode("ascii")))
                scope = {**scope, "headers": headers}
        await self.app(scope, receive, send)
