# -*- coding: utf-8 -*-
"""Runtime configuration read from the environment."""

import os
from dataclasses import dataclass

TRUE_VALUES = ("1", "true", "yes", "on")


class ConfigError(ValueError):
    """Raised when the configuration cannot be used as given."""


def as_bool(value):
    """Coerce an environment string to a boolean."""
    return str(value).strip().lower() in TRUE_VALUES


def as_seconds(name, value):
    """Return `value` as a positive number of seconds.

    :param name: the variable the value came from, for the message
    :param value: the raw string
    :raises ConfigError: when `value` is not a positive number
    """
    try:
        seconds = float(value)
    except ValueError:
        raise ConfigError(
            "{} must be a number of seconds, not {!r}".format(name, value))
    if seconds <= 0:
        raise ConfigError("{} must be positive, not {}".format(name, value))
    return seconds


def require(environ, name, example):
    """Return the variable `name` from `environ`, or raise.

    :param environ: the mapping to read from
    :param name: the variable name
    :param example: an example value for the message
    :raises ConfigError: when the variable is unset or empty
    """
    value = environ.get(name, "").strip()
    if not value:
        raise ConfigError("{} is required, e.g. {}".format(name, example))
    return value


@dataclass
class Settings:
    """Connection settings for a SENAITE instance."""

    base_url: str
    username: str = ""
    password: str = ""
    timeout: float = 30.0
    compose_timeout: float = 300.0
    verify_ssl: bool = True

    @classmethod
    def from_env(cls, environ=None):
        """Build settings from SENAITE_* environment variables.

        There is no default login. A server that falls back to a
        well-known password either talks to a site as its admin by
        accident or fails with errors that do not name the cause.

        :param environ: the mapping to read, defaults to `os.environ`
        :returns: a populated :class:`Settings` instance
        :raises ConfigError: when a required variable is missing or a
            value cannot be used
        """
        env = os.environ if environ is None else environ
        url = require(env, "SENAITE_URL", "http://localhost:8080/senaite")
        return cls(
            base_url=url.rstrip("/"),
            username=require(env, "SENAITE_USERNAME", "admin"),
            password=require(env, "SENAITE_PASSWORD", "secret"),
            timeout=as_seconds(
                "SENAITE_TIMEOUT", env.get("SENAITE_TIMEOUT", "30")),
            compose_timeout=as_seconds(
                "SENAITE_COMPOSE_TIMEOUT",
                env.get("SENAITE_COMPOSE_TIMEOUT", "300")),
            verify_ssl=as_bool(env.get("SENAITE_VERIFY_SSL", "true")),
        )
