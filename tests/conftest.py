# -*- coding: utf-8 -*-
"""Shared fixtures: run async tests on asyncio through anyio's plugin."""

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"
