# -*- coding: utf-8 -*-
"""Offline tests: the server as an MCP host sees it."""

import httpx
import pytest

from senaite_mcp.client import SenaiteClient
from senaite_mcp.client import SenaiteError
from senaite_mcp.config import Settings
from senaite_mcp.server import build_server
from senaite_mcp.server import check_login

pytestmark = pytest.mark.anyio

SETTINGS = Settings(base_url="http://nohost/senaite", username="agent")


def make_client(handler):
    return SenaiteClient(SETTINGS, transport=httpx.MockTransport(handler))


def current_user(authenticated):
    """Return a handler answering users/current."""
    item = {"username": "agent", "authenticated": authenticated}
    return lambda request: httpx.Response(200, json={"items": [item]})


async def test_lists_every_tool():
    server = build_server(make_client(current_user(True)))
    names = [tool.name for tool in await server.list_tools()]
    assert names == [
        "senaite_version", "senaite_search", "senaite_get",
        "senaite_create", "senaite_update", "senaite_delete",
        "senaite_do_transition", "senaite_compose_reference",
        "senaite_compose"]


async def test_no_self_parameter():
    server = build_server(make_client(current_user(True)))
    for tool in await server.list_tools():
        assert "self" not in tool.inputSchema.get("properties", {})


def test_remote_host_is_accepted_when_listed():
    server = build_server(
        make_client(current_user(True)), host="0.0.0.0",
        allowed_hosts=["mcp.example.com"])
    security = server.settings.transport_security
    assert security.allowed_hosts == ["mcp.example.com"]


def test_bound_publicly_without_a_list():
    server = build_server(make_client(current_user(True)), host="0.0.0.0")
    assert server.settings.transport_security is None


async def check(handler, monkeypatch):
    """Run check_login against `handler`."""
    original = SenaiteClient.__init__

    def init(self, settings, transport=None):
        original(self, settings, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(SenaiteClient, "__init__", init)
    return await check_login(SETTINGS)


async def test_check_login(monkeypatch):
    assert await check(current_user(True), monkeypatch) == "agent"


async def test_check_login_refused(monkeypatch):
    with pytest.raises(SenaiteError) as info:
        await check(current_user(False), monkeypatch)
    assert info.value.status == 401
    assert "does not accept the login 'agent'" in str(info.value)


async def test_annotations():
    server = build_server(make_client(current_user(True)))
    tools = {tool.name: tool for tool in await server.list_tools()}
    assert tools["senaite_search"].annotations.readOnlyHint is True
    assert tools["senaite_create"].annotations.readOnlyHint is False
    assert tools["senaite_compose"].annotations.idempotentHint is True
