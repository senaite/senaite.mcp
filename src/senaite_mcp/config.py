# -*- coding: utf-8 -*-
"""Runtime configuration read from the environment."""

import os
from dataclasses import dataclass

TRUE_VALUES = ("1", "true", "yes", "on")


def as_bool(value):
    """Coerce an environment string to a boolean."""
    return str(value).strip().lower() in TRUE_VALUES


@dataclass
class Settings:
    """Connection settings for a SENAITE instance."""

    base_url: str
    username: str = "admin"
    password: str = "admin"
    timeout: float = 30.0
    verify_ssl: bool = True

    @classmethod
    def from_env(cls):
        """Build settings from SENAITE_* environment variables.

        :returns: a populated :class:`Settings` instance
        :raises RuntimeError: when `SENAITE_URL` is not set
        """
        url = os.environ.get("SENAITE_URL", "").rstrip("/")
        if not url:
            raise RuntimeError(
                "SENAITE_URL is required, e.g. "
                "http://localhost:8080/senaite")
        return cls(
            base_url=url,
            username=os.environ.get("SENAITE_USERNAME", "admin"),
            password=os.environ.get("SENAITE_PASSWORD", "admin"),
            timeout=float(os.environ.get("SENAITE_TIMEOUT", "30")),
            verify_ssl=as_bool(os.environ.get("SENAITE_VERIFY_SSL", "true")),
        )
