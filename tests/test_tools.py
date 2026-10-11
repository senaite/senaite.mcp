# -*- coding: utf-8 -*-
"""Offline tests: what each tool puts on the wire."""

import httpx
import pytest

from senaite_mcp.client import SenaiteClient
from senaite_mcp.config import Settings
from senaite_mcp.tools import Tools

pytestmark = pytest.mark.anyio

UID = "a" * 32


@pytest.fixture
def sent():
    return []


@pytest.fixture
async def tools(sent):
    def handler(request):
        sent.append(request)
        return httpx.Response(200, json={"items": []})
    client = SenaiteClient(
        Settings(base_url="http://nohost/senaite"),
        transport=httpx.MockTransport(handler))
    yield Tools(client)
    await client.close()


async def test_search_pages(tools, sent):
    await tools.senaite_search("Client", limit=10, b_start=20)
    assert dict(sent[-1].url.params) == {
        "portal_type": "Client", "limit": "10", "b_start": "20"}


async def test_search_arguments_win_over_query(tools, sent):
    await tools.senaite_search(
        query={"limit": 999, "review_state": "sample_due"}, limit=5)
    params = dict(sent[-1].url.params)
    assert params["limit"] == "5"
    assert params["review_state"] == "sample_due"


async def test_listing_pages(tools, sent):
    await tools.senaite_get(resource="Client", limit=5, b_start=5)
    assert dict(sent[-1].url.params) == {"limit": "5", "b_start": "5"}


async def test_get_by_uid_has_no_batch(tools, sent):
    await tools.senaite_get(uid=UID)
    assert not sent[-1].url.params


async def test_create_without_fields(tools, sent):
    await tools.senaite_create("Client", "/senaite/clients")
    assert sent[-1].url.path.endswith("/Client/create")
