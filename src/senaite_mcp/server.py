# -*- coding: utf-8 -*-
"""FastMCP server exposing SENAITE JSON API operations as tools."""

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from .client import SenaiteClient
from .config import Settings

mcp = FastMCP("senaite")

_client = None


def client():
    """Return the process-wide client, built lazily from the env."""
    global _client
    if _client is None:
        _client = SenaiteClient(Settings.from_env())
    return _client


@mcp.tool()
def senaite_version() -> dict:
    """Return the SENAITE JSON API version and endpoint info."""
    return client().version()


@mcp.tool()
def senaite_search(
    portal_type: str = "",
    query: Optional[dict] = None,
    limit: int = 25,
) -> dict:
    """Search SENAITE content.

    :param portal_type: restrict to a content type, e.g. `Client`
    :param query: extra JSON API query params (catalog indexes, sorting)
    :param limit: maximum number of items to return
    """
    params: dict[str, Any] = dict(query or {})
    if portal_type:
        params["portal_type"] = portal_type
    params.setdefault("limit", limit)
    return client().search(params)


@mcp.tool()
def senaite_get(uid: str = "", resource: str = "") -> dict:
    """Fetch a record by uid, or list a resource / portal_type.

    :param uid: 32-char object uid
    :param resource: plural resource or portal_type name
    """
    return client().get(uid=uid or None, resource=resource or None)


@mcp.tool()
def senaite_create(
    portal_type: str,
    parent_path: str,
    fields: Optional[dict] = None,
) -> dict:
    """Create a content object.

    :param portal_type: content type to create, e.g. `Client`
    :param parent_path: physical path of the container, e.g.
        `/senaite/clients`
    :param fields: field values for the new object
    """
    return client().create(portal_type, parent_path, fields or {})


@mcp.tool()
def senaite_update(uid: str, fields: dict) -> dict:
    """Update the object addressed by `uid` with `fields`."""
    return client().update(uid, fields)


@mcp.tool()
def senaite_delete(uid: str) -> dict:
    """Delete the object addressed by `uid`."""
    return client().delete(uid)


@mcp.tool()
def senaite_do_transition(uid: str, transition: str) -> dict:
    """Fire a workflow transition on an object.

    :param uid: 32-char object uid
    :param transition: workflow transition id, e.g. `receive`, `submit`,
        `verify`, `publish`
    """
    return client().do_transition(uid, transition)


def main():
    """Console-script entry point: run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
