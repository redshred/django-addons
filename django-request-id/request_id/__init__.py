from __future__ import annotations

from uuid import uuid4

from .local import Local, release_local  # noqa: F401  (re-exported for back-compat)

__version__ = "2.0.0"

local = Local()


def generate_request_id() -> str:
    return str(uuid4())


def get_current_request_id() -> str:
    from .local import get as _get

    return _get()


__all__ = ["generate_request_id", "get_current_request_id", "local", "release_local"]
