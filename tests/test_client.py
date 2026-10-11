# -*- coding: utf-8 -*-
"""Offline tests: verify each client method maps to the right route.

These do not hit a live instance. An httpx mock transport records the
request the client really sends, so the URL, the verb, the query and
the body are checked as they would go over the wire.
"""

import json

import httpx
import pytest

from senaite_mcp.client import SenaiteClient
from senaite_mcp.config import Settings

pytestmark = pytest.mark.anyio

API = "/senaite/@@API/senaite/v1"
UID = "a" * 32


class Recorder:
    """Answer every request with `{"ok": true}` and keep what was sent."""

    def __init__(self):
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return httpx.Response(200, json={"ok": True})

    @property
    def last(self):
        return self.requests[-1]


def body(request):
    """Return the JSON body of a recorded request, or None."""
    if not request.content:
        return None
    return json.loads(request.content)


@pytest.fixture
def recorder():
    return Recorder()


@pytest.fixture
async def client(recorder):
    settings = Settings(base_url="http://nohost/senaite")
    c = SenaiteClient(settings, transport=httpx.MockTransport(recorder))
    yield c
    await c.close()


async def test_api_url(client):
    assert client.api_url == "http://nohost/senaite/@@API/senaite/v1"


async def test_version(client, recorder):
    await client.version()
    assert recorder.last.method == "GET"
    assert recorder.last.url.path == API + "/version"


async def test_search(client, recorder):
    await client.search({"portal_type": "Client", "limit": 5})
    assert recorder.last.url.path == API + "/search"
    assert dict(recorder.last.url.params) == {
        "portal_type": "Client", "limit": "5"}


async def test_get_by_uid(client, recorder):
    await client.get(uid=UID)
    assert recorder.last.url.path == API + "/" + UID


async def test_get_resource_and_uid(client, recorder):
    await client.get(uid=UID, resource="Client")
    assert recorder.last.url.path == API + "/Client/" + UID


async def test_get_resource_listing(client, recorder):
    await client.get(resource="Client")
    assert recorder.last.url.path == API + "/Client"


async def test_get_requires_argument(client):
    with pytest.raises(ValueError):
        await client.get()


async def test_create(client, recorder):
    await client.create("Client", "/senaite/clients", {"title": "ACME"})
    assert recorder.last.method == "POST"
    assert recorder.last.url.path == API + "/Client/create"
    assert body(recorder.last) == {
        "title": "ACME", "parent_path": "/senaite/clients"}


async def test_update(client, recorder):
    await client.update(UID, {"title": "New"})
    assert recorder.last.method == "PATCH"
    assert recorder.last.url.path == API + "/" + UID
    assert body(recorder.last) == {"title": "New"}


async def test_delete(client, recorder):
    await client.delete(UID)
    assert recorder.last.method == "DELETE"
    assert recorder.last.url.path == API + "/" + UID


async def test_do_transition(client, recorder):
    await client.do_transition(UID, "receive")
    assert recorder.last.method == "PATCH"
    assert body(recorder.last) == {"transition": "receive"}


async def test_compose(client, recorder):
    spec = {"version": 1, "setup": [], "content": []}
    await client.compose(spec)
    assert recorder.last.method == "POST"
    assert recorder.last.url.path == API + "/compose"
    assert body(recorder.last) == spec


async def test_compose_reference(client, recorder):
    await client.compose_reference()
    assert recorder.last.url.path == API + "/compose/reference"


async def test_sends_credentials(client, recorder):
    await client.version()
    assert recorder.last.headers["Authorization"].startswith("Basic ")
