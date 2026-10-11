# -*- coding: utf-8 -*-
"""Offline tests: settings from the environment and from the flags."""

import pytest

from senaite_mcp.config import ConfigError
from senaite_mcp.config import Settings
from senaite_mcp.config import as_bool
from senaite_mcp.server import load_settings
from senaite_mcp.server import parse_args
from senaite_mcp.server import split_hosts

ENV = {
    "SENAITE_URL": "http://lims/senaite/",
    "SENAITE_USERNAME": "agent",
    "SENAITE_PASSWORD": "secret",
}


def env(**changes):
    """Return the base environment with `changes` applied."""
    result = dict(ENV)
    result.update(changes)
    return result


def test_from_env():
    settings = Settings.from_env(ENV)
    assert settings.base_url == "http://lims/senaite"
    assert settings.username == "agent"
    assert settings.timeout == 30
    assert settings.compose_timeout == 300
    assert settings.verify_ssl is True


@pytest.mark.parametrize("name", list(ENV))
def test_required(name):
    with pytest.raises(ConfigError) as info:
        Settings.from_env(env(**{name: ""}))
    assert name in str(info.value)


@pytest.mark.parametrize("value", ["abc", "0", "-1"])
def test_timeout_must_be_positive_seconds(value):
    with pytest.raises(ConfigError):
        Settings.from_env(env(SENAITE_TIMEOUT=value))


@pytest.mark.parametrize("value,expected", [
    ("true", True), ("1", True), ("Yes", True), ("false", False),
    ("0", False), ("", False)])
def test_as_bool(value, expected):
    assert as_bool(value) is expected


def test_flags_override_env():
    args = parse_args(["--url", "http://other/site2", "--username", "bob"],
                      environ={})
    settings = load_settings(args, environ=ENV)
    assert settings.base_url == "http://other/site2"
    assert settings.username == "bob"
    assert settings.password == "secret"


def test_no_password_flag():
    with pytest.raises(SystemExit):
        parse_args(["--password", "secret"], environ={})


def test_server_defaults():
    args = parse_args([], environ={})
    assert (args.transport, args.host, args.port) == (
        "stdio", "127.0.0.1", 7980)
    assert args.allowed_hosts == []


def test_server_env():
    args = parse_args([], environ={
        "SENAITE_MCP_TRANSPORT": "streamable-http",
        "SENAITE_MCP_PORT": "9000",
        "SENAITE_MCP_ALLOWED_HOSTS": "a.example.com, b.example.com:443"})
    assert args.transport == "streamable-http"
    assert args.port == 9000
    assert args.allowed_hosts == ["a.example.com", "b.example.com:443"]


def test_split_hosts():
    assert split_hosts(None) == []
    assert split_hosts(" a ,, b ") == ["a", "b"]
