from __future__ import annotations

import asyncio

from django.http import JsonResponse
from django.urls import path

from request_id import get_current_request_id


def sync_view(request):
    return JsonResponse(
        {
            "on_request": getattr(request, "request_id", ""),
            "from_contextvar": get_current_request_id(),
        }
    )


async def async_view(request):
    pre = get_current_request_id()
    await asyncio.sleep(0.05)
    post = get_current_request_id()
    return JsonResponse(
        {
            "on_request": getattr(request, "request_id", ""),
            "pre_sleep": pre,
            "post_sleep": post,
        }
    )


urlpatterns = [
    path("sync/", sync_view),
    path("async/", async_view),
]
