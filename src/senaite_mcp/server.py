# -*- coding: utf-8 -*-
"""FastMCP server exposing SENAITE JSON API operations as tools."""

import argparse
import os
import sys
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from senaite_mcp import __version__
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


def parse_args(argv=None):
    """Parse command-line arguments (flags default to env vars).

    The host defaults to localhost on purpose: a reachable MCP endpoint
    grants callers the same power over SENAITE as this server's
    credentials, so only bind a public interface behind authentication
    (reverse proxy with TLS, SSH tunnel or VPN).
    """
    parser = argparse.ArgumentParser(
        prog="senaite-mcp",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="MCP server exposing the SENAITE JSON API to agents.",
        epilog=(
            "connection (environment variables):\n"
            "  SENAITE_URL          site URL, e.g. "
            "http://localhost:8080/senaite (required)\n"
            "  SENAITE_USERNAME     default: admin\n"
            "  SENAITE_PASSWORD     default: admin\n"
            "  SENAITE_TIMEOUT      request timeout, seconds "
            "(default: 30)\n"
            "  SENAITE_VERIFY_SSL   verify TLS certs (default: true)\n\n"
            "examples:\n"
            "  senaite-mcp                 # stdio (a host launches this)\n"
            "  senaite-mcp --transport streamable-http --port 7980\n"))
    parser.add_argument(
        "--transport", choices=["stdio", "streamable-http", "sse"],
        default=os.environ.get("SENAITE_MCP_TRANSPORT", "stdio"),
        help="transport to run (default: stdio, or $SENAITE_MCP_TRANSPORT)")
    parser.add_argument(
        "--host", default=os.environ.get("SENAITE_MCP_HOST", "127.0.0.1"),
        help="bind host for network transports (default: 127.0.0.1)")
    parser.add_argument(
        "--port", type=int,
        default=int(os.environ.get("SENAITE_MCP_PORT", "7980")),
        help="bind port for network transports (default: 7980)")
    parser.add_argument(
        "--version", action="version",
        version="senaite-mcp {}".format(__version__))
    return parser.parse_args(argv)


def main(argv=None):
    """Console-script entry point: run the MCP server."""
    args = parse_args(argv)
    target = os.environ.get("SENAITE_URL", "<SENAITE_URL unset>")
    if args.transport != "stdio":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        listen = "{}:{}".format(args.host, args.port)
    else:
        listen = "stdio"
    # Log to stderr: in stdio mode stdout carries the MCP protocol.
    print("senaite-mcp starting: transport={} listen={} target={}".format(
        args.transport, listen, target), file=sys.stderr)
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
