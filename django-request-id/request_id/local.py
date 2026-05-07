"""
Per-request storage backed by ``contextvars.ContextVar``.

Replaces the older threadlocal/greenlet-keyed implementation: under ASGI, many
concurrent requests share the same OS thread, so a thread-keyed store would
mix request IDs across in-flight requests. ``ContextVar`` is scoped to the
current asyncio task (or sync call stack), which is the correct boundary.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

__all__ = ["get", "set", "reset", "Local", "release_local"]

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get() -> str:
    return _request_id_var.get()


def set(value: str) -> Token[str]:  # noqa: A001 - public API name predates builtin shadow lint
    return _request_id_var.set(value)


def reset(token: Token[str]) -> None:
    _request_id_var.reset(token)


class Local:
    """
    Backwards-compatible shim for the pre-2.0 ``request_id.local`` object.

    Old code did ``local.request_id = "abc"`` / ``local.request_id``. We map
    those reads and writes onto the module-level ContextVar so existing
    callers keep working. New code should use ``get()`` / ``set()`` /
    ``reset()`` directly.
    """

    __slots__ = ()

    def __getattr__(self, name: str) -> str:
        if name != "request_id":
            raise AttributeError(name)
        value = _request_id_var.get()
        if not value:
            raise AttributeError(name)
        return value

    def __setattr__(self, name: str, value: str) -> None:
        if name != "request_id":
            raise AttributeError(name)
        _request_id_var.set(value)

    def __delattr__(self, name: str) -> None:
        if name != "request_id":
            raise AttributeError(name)
        _request_id_var.set("")


def release_local(local: Local) -> None:
    """Clear the request_id for the current context."""
    _request_id_var.set("")
