#!/usr/bin/env python
"""
Demo script. Run with::

    uv run uvicorn demo:application
"""

from __future__ import annotations

import logging
import os

from django.conf import settings

basename = os.path.splitext(os.path.basename(__file__))[0]


def rel(*path: str) -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), *path)).replace("\\", "/")


if not settings.configured:
    settings.configure(
        DEBUG=True,
        ALLOWED_HOSTS=["*"],
        TIME_ZONE="UTC",
        USE_TZ=True,
        INSTALLED_APPS=["request_id"],
        ROOT_URLCONF=basename,
        ASGI_APPLICATION=f"{basename}.application",
        SECRET_KEY="demo-not-for-production",
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [rel("tests", "templates")],
                "OPTIONS": {
                    "context_processors": ["django.template.context_processors.request"],
                },
            },
        ],
        MIDDLEWARE=["request_id.middleware.RequestIdMiddleware"],
        LOGGING={
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_id": {"()": "request_id.logging.RequestIdFilter"},
            },
            "formatters": {
                "console": {
                    "format": "%(asctime)s - %(levelname)-5s [%(name)s] request_id=%(request_id)s %(message)s",
                    "datefmt": "%H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "level": "DEBUG",
                    "filters": ["request_id"],
                    "class": "logging.StreamHandler",
                    "formatter": "console",
                },
            },
            "loggers": {"": {"level": "DEBUG", "handlers": ["console"]}},
        },
    )

import django

django.setup()

from django.core.asgi import get_asgi_application
from django.urls import path
from django.views.generic.base import TemplateView

from request_id import get_current_request_id
from request_id.asgi import AddRequestIdHeaderMiddleware

logger = logging.getLogger("view")


class HelloView(TemplateView):
    template_name = "base.html"

    def get(self, request, *args, **kwargs):
        logger.info("handling request")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        logger.info("preparing context data")
        return super().get_context_data(current_request_val=get_current_request_id(), **kwargs)

    def render_to_response(self, context, **response_kwargs):
        logger.info("rendering template")
        return super().render_to_response(context, **response_kwargs)


urlpatterns = [path("", HelloView.as_view())]

application = AddRequestIdHeaderMiddleware(get_asgi_application())
