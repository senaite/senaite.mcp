# -*- coding: utf-8 -*-
"""Command line entry point: check the configuration, then serve."""

import argparse
import asyncio
import logging
import os
import sys

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from senaite_mcp import __version__
from senaite_mcp.client import SenaiteClient
from senaite_mcp.client import SenaiteError
from senaite_mcp.config import ConfigError
from senaite_mcp.config import Settings
from senaite_mcp.tools import Tools

TRANSPORTS = ("stdio", "streamable-http", "sse")

# Content types `--check` counts to show the login sees the content
CHECK_TYPES = ("Client", "Contact", "AnalysisService", "AnalysisRequest")

EPILOG = """\
connection (environment variables):
  SENAITE_URL              site URL, e.g. http://localhost:8080/senaite
  SENAITE_USERNAME         login user (required)
  SENAITE_PASSWORD         login password (required, no flag on purpose:
                           a flag shows up in the process list)
  SENAITE_TIMEOUT          seconds per request (default: 30)
  SENAITE_COMPOSE_TIMEOUT  seconds per compose (default: 300)
  SENAITE_VERIFY_SSL       verify TLS certificates (default: true)

server (environment variables, the flags override them):
  SENAITE_MCP_TRANSPORT      stdio, streamable-http or sse
  SENAITE_MCP_HOST           bind host (default: 127.0.0.1)
  SENAITE_MCP_PORT           bind port (default: 7980)
  SENAITE_MCP_ALLOWED_HOSTS  comma-separated Host headers to accept

examples:
  senaite-mcp --check          # test the login, then exit
  senaite-mcp                  # stdio, an MCP host launches this
  senaite-mcp --transport streamable-http --port 7980
"""


def split_hosts(value):
    """Split a comma-separated host list, dropping empty entries."""
    return [host.strip() for host in (value or "").split(",")
            if host.strip()]


def parse_args(argv=None, environ=None):
    """Parse command-line arguments, which default to the environment.

    The host defaults to localhost on purpose: a reachable MCP endpoint
    grants callers the same power over SENAITE as this server's
    credentials, so only bind a public interface behind authentication
    (reverse proxy with TLS, SSH tunnel or VPN).
    """
    env = os.environ if environ is None else environ
    parser = argparse.ArgumentParser(
        prog="senaite-mcp",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="MCP server exposing the SENAITE JSON API to agents.",
        epilog=EPILOG)
    parser.add_argument(
        "--url", help="SENAITE site URL (overrides $SENAITE_URL)")
    parser.add_argument(
        "--username", help="login user (overrides $SENAITE_USERNAME)")
    parser.add_argument(
        "--check", action="store_true",
        help="test the connection and the login, then exit")
    parser.add_argument(
        "--transport", choices=TRANSPORTS,
        default=env.get("SENAITE_MCP_TRANSPORT", "stdio"),
        help="transport to run (default: stdio)")
    parser.add_argument(
        "--host", default=env.get("SENAITE_MCP_HOST", "127.0.0.1"),
        help="bind host for network transports (default: 127.0.0.1)")
    parser.add_argument(
        "--port", type=int, default=int(env.get("SENAITE_MCP_PORT", "7980")),
        help="bind port for network transports (default: 7980)")
    parser.add_argument(
        "--allowed-host", action="append", dest="allowed_hosts",
        default=split_hosts(env.get("SENAITE_MCP_ALLOWED_HOSTS")),
        help="a Host header to accept, e.g. mcp.example.com:443; "
             "repeat for more")
    parser.add_argument(
        "--version", action="version",
        version="senaite-mcp {}".format(__version__))
    return parser.parse_args(argv)


def load_settings(args, environ=None):
    """Return the connection settings, the flags winning over the env.

    :raises ConfigError: when the result is not usable
    """
    env = dict(os.environ if environ is None else environ)
    if args.url:
        env["SENAITE_URL"] = args.url
    if args.username:
        env["SENAITE_USERNAME"] = args.username
    return Settings.from_env(env)


def transport_security(allowed_hosts):
    """Return the Host header checks for a network transport.

    The SDK protects a server bound to localhost against DNS rebinding
    on its own, and accepts only localhost Host headers there. Bound
    anywhere else it checks nothing, unless the hosts are listed.

    :param allowed_hosts: Host header values to accept, may be empty
    :returns: settings for the SDK, or None for its default
    """
    if not allowed_hosts:
        return None
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(allowed_hosts))


def build_server(client, host="127.0.0.1", port=7980, allowed_hosts=()):
    """Return a FastMCP server with every tool bound to `client`.

    Built here rather than at import time, because the SDK fixes its
    Host header checks from the bind host when the server is created.
    """
    server = FastMCP(
        "senaite", host=host, port=port,
        transport_security=transport_security(allowed_hosts))
    for tool in Tools(client).all():
        server.add_tool(tool)
    return server


async def check_login(settings):
    """Return the name the site knows this login by, or raise.

    :raises SenaiteError: when the site cannot be reached, or answers
        the login as an anonymous caller
    """
    client = SenaiteClient(settings)
    try:
        user = await client.current_user()
    finally:
        await client.close()
    if not user.get("authenticated"):
        raise SenaiteError(
            "{} does not accept the login {!r}: check SENAITE_USERNAME "
            "and SENAITE_PASSWORD".format(
                settings.base_url, settings.username), status=401)
    return user.get("username")


async def report(settings):
    """Print the API version and a few content counts, for `--check`."""
    client = SenaiteClient(settings)
    try:
        version = await client.version()
        print("api_url: {}".format(client.api_url))
        print("version: {}".format(version.get("version")))
        for portal_type in CHECK_TYPES:
            found = await client.search(
                {"portal_type": portal_type, "limit": 1})
            print("  {:<16} {}".format(portal_type, found.get("count")))
    finally:
        await client.close()


def fail(message):
    """Print `message` to stderr and return the exit status."""
    print("senaite-mcp: {}".format(message), file=sys.stderr)
    return 1


def main(argv=None):
    """Console-script entry point: run the MCP server."""
    # httpx logs one INFO line per request; keep the server's stderr tidy.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    args = parse_args(argv)
    try:
        settings = load_settings(args)
    except ConfigError as exc:
        return fail(exc)

    # A wrong login is final, so stop. An unreachable site may only
    # not be up yet, so serve anyway: each call reports it until it is.
    try:
        username = asyncio.run(check_login(settings))
    except SenaiteError as exc:
        if exc.status is not None or args.check:
            return fail(exc)
        username = None
        print("senaite-mcp: warning: {}".format(exc), file=sys.stderr)

    if args.check:
        print("login:   {}".format(username))
        asyncio.run(report(settings))
        return 0

    server = build_server(
        SenaiteClient(settings), args.host, args.port, args.allowed_hosts)
    listen = "stdio"
    if args.transport != "stdio":
        listen = "{}:{}".format(args.host, args.port)
    # Log to stderr: in stdio mode stdout carries the MCP protocol.
    print("senaite-mcp {} starting: transport={} listen={} target={} "
          "user={}".format(__version__, args.transport, listen,
                           settings.base_url, username), file=sys.stderr)
    server.run(transport=args.transport)
    return 0


if __name__ == "__main__":
    sys.exit(main())
