from __future__ import annotations

from django.conf import settings

from .defaults import DEFAULT_REQUEST_ID_HEADER_NAME

REQUEST_ID_HEADER: str = getattr(settings, "REQUEST_ID_HEADER", DEFAULT_REQUEST_ID_HEADER_NAME)
"""
Default header name as defined in
`heroku request-id <https://devcenter.heroku.com/articles/http-request-id>`_
"""
