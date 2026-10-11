# -*- coding: utf-8 -*-
"""Offline tests: what an agent is told when a call goes wrong.

An MCP host passes only the message of an exception on to the agent,
so every message has to name the status and the likely cause.
"""

import httpx
import pytest

from senaite_mcp.client import SenaiteClient
from senaite_mcp.client import SenaiteError
from senaite_mcp.client import require_uid
from senaite_mcp.config import Settings

pytestmark = pytest.mark.anyio

URL = "http://nohost/senaite"


def make_client(handler):
    """Return a client whose every request is answered by `handler`."""
    settings = Settings(base_url=URL, timeout=5)
    return SenaiteClient(settings, transport=httpx.MockTransport(handler))


def answer(*args, **kw):
    """Return a handler that answers every request with one response."""
    return lambda request: httpx.Response(*args, **kw)


def fail(exc_class):
    """Return a handler that fails every request with `exc_class`."""
    def handler(request):
        raise exc_class("boom", request=request)
    return handler


async def call(handler, method="version", *args):
    """Run one client call against `handler`, return the error."""
    client = make_client(handler)
    with pytest.raises(SenaiteError) as info:
        await getattr(client, method)(*args)
    await client.close()
    return info.value


async def test_error_envelope_carries_status():
    error = await call(answer(
        400, json={"success": False, "message": "Bad field",
                   "type": "ValueError"}))
    assert str(error) == "400 Bad Request: Bad field"
    assert error.status == 400
    assert error.error_type == "ValueError"


async def test_success_false_on_200_is_an_error():
    error = await call(answer(
        200, json={"success": False, "message": "Not allowed"}))
    assert "Not allowed" in str(error)


async def test_compose_missing_names_the_add_on():
    error = await call(answer(404, text="<html>Not found</html>"),
                       "compose", {})
    assert "Install senaite.composer on " + URL in str(error)


async def test_html_error_page():
    error = await call(answer(500, text="<html>oops</html>"))
    assert str(error) == "Non-JSON response (500 Internal Server Error)"


async def test_redirect_to_login_form():
    error = await call(answer(
        302, headers={"Location": URL + "/login"}))
    assert "username or password is wrong" in str(error)


async def test_json_that_is_not_an_object():
    error = await call(answer(200, json=["a", "b"]))
    assert "not a JSON object" in str(error)


async def test_unreachable_site():
    error = await call(fail(httpx.ConnectError))
    assert str(error).startswith("Cannot reach " + URL)


async def test_timeout():
    error = await call(fail(httpx.ReadTimeout))
    assert str(error) == "No answer from {} within 5 seconds".format(URL)


@pytest.mark.parametrize("uid", ["0", "a" * 32, "0123456789abcdef" * 2])
def test_require_uid_accepts(uid):
    assert require_uid(uid) == uid


@pytest.mark.parametrize("uid", [
    "", None, "a" * 31, "A" * 32, "../../manage_main", "a" * 32 + "/x"])
def test_require_uid_refuses(uid):
    with pytest.raises(ValueError):
        require_uid(uid)


@pytest.mark.parametrize("method", ["update", "delete", "do_transition"])
async def test_writes_refuse_an_empty_uid(method):
    client = make_client(answer(200, json={}))
    args = {"update": ("", {}), "delete": ("",),
            "do_transition": ("", "receive")}[method]
    with pytest.raises(ValueError):
        await getattr(client, method)(*args)
    await client.close()
