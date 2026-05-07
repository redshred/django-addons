from __future__ import annotations

import asyncio
import json

import pytest
from django.test import AsyncClient, Client


def test_sync_view_uses_inbound_header():
    client = Client()
    response = client.get("/sync/", headers={"x-request-id": "sync-incoming-123"})
    body = json.loads(response.content)
    assert body["on_request"] == "sync-incoming-123"
    assert body["from_contextvar"] == "sync-incoming-123"


def test_sync_view_generates_when_missing():
    client = Client()
    response = client.get("/sync/")
    body = json.loads(response.content)
    assert body["on_request"]
    assert body["on_request"] == body["from_contextvar"]


async def test_async_view_uses_inbound_header():
    client = AsyncClient()
    response = await client.get("/async/", headers={"x-request-id": "async-incoming-abc"})
    body = json.loads(response.content)
    assert body["on_request"] == "async-incoming-abc"
    assert body["pre_sleep"] == "async-incoming-abc"
    assert body["post_sleep"] == "async-incoming-abc"


async def test_concurrent_async_requests_do_not_leak_request_id():
    """
    Regression test: under ASGI, two concurrent requests share an OS thread.
    The old threadlocal-based implementation would leak request IDs across
    them. With ContextVar, each task sees only its own ID across awaits.
    """

    async def hit(rid: str) -> dict:
        client = AsyncClient()
        response = await client.get("/async/", headers={"x-request-id": rid})
        return json.loads(response.content)

    a, b = await asyncio.gather(hit("REQ-A"), hit("REQ-B"))

    assert a["on_request"] == "REQ-A"
    assert a["pre_sleep"] == "REQ-A"
    assert a["post_sleep"] == "REQ-A"
    assert b["on_request"] == "REQ-B"
    assert b["pre_sleep"] == "REQ-B"
    assert b["post_sleep"] == "REQ-B"


@pytest.mark.parametrize("path", ["/sync/", "/async/"])
def test_logging_filter_picks_up_request_id(path, caplog):
    import logging

    from request_id.logging import RequestIdFilter

    logger = logging.getLogger("test.request_id")
    logger.addFilter(RequestIdFilter())

    client = Client()
    with caplog.at_level(logging.INFO, logger="test.request_id"):
        client.get(path, headers={"x-request-id": "filter-test"})
        logger.info("hello")

    record = next(r for r in caplog.records if r.message == "hello")
    assert hasattr(record, "request_id")
