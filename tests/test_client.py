# -*- coding: utf-8 -*-
"""Offline tests: verify each client method maps to the right route.

These do not hit a live instance; they capture the (method, path,
params, payload) that `request` would send and assert the JSON API
contract.
"""

import pytest

from senaite_mcp.client import SenaiteClient
from senaite_mcp.config import Settings


@pytest.fixture
def client(monkeypatch):
    settings = Settings(base_url="http://nohost/senaite")
    c = SenaiteClient(settings)
    calls = []

    def fake_request(method, path, params=None, payload=None):
        calls.append((method, path, params, payload))
        return {"ok": True}

    monkeypatch.setattr(c, "request", fake_request)
    c.calls = calls
    return c


def test_api_url(client):
    assert client.api_url == "http://nohost/senaite/@@API/senaite/v1"


def test_version(client):
    client.version()
    assert client.calls[-1] == ("GET", "version", None, None)


def test_search(client):
    client.search({"portal_type": "Client", "limit": 5})
    method, path, params, _ = client.calls[-1]
    assert (method, path) == ("GET", "search")
    assert params == {"portal_type": "Client", "limit": 5}


def test_get_by_uid(client):
    client.get(uid="a" * 32)
    assert client.calls[-1] == ("GET", "a" * 32, None, None)


def test_get_resource_and_uid(client):
    client.get(uid="a" * 32, resource="Client")
    assert client.calls[-1][1] == "Client/" + "a" * 32


def test_get_resource_listing(client):
    client.get(resource="Client")
    assert client.calls[-1] == ("GET", "Client", None, None)


def test_get_requires_argument(client):
    with pytest.raises(ValueError):
        client.get()


def test_create(client):
    client.create("Client", "/senaite/clients", {"title": "ACME"})
    method, path, _, payload = client.calls[-1]
    assert (method, path) == ("POST", "Client/create")
    assert payload == {"title": "ACME", "parent_path": "/senaite/clients"}


def test_update(client):
    client.update("a" * 32, {"title": "New"})
    assert client.calls[-1] == ("PATCH", "a" * 32, None, {"title": "New"})


def test_delete(client):
    client.delete("a" * 32)
    assert client.calls[-1] == ("DELETE", "a" * 32, None, None)


def test_do_transition(client):
    client.do_transition("a" * 32, "receive")
    assert client.calls[-1] == (
        "PATCH", "a" * 32, None, {"transition": "receive"})


def test_compose(client):
    spec = {"version": 1, "setup": [], "content": []}
    client.compose(spec)
    assert client.calls[-1] == ("POST", "compose", None, spec)
