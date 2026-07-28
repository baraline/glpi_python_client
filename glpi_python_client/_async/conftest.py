"""Fixtures shared by every unit test in this tree.

Generated into the sync tree alongside the modules it serves, so both
surfaces get a fixture that builds the client they actually test.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from glpi_python_client import AsyncGlpiClient
from glpi_python_client._async._testing import make_client


@pytest.fixture
async def client() -> AsyncIterator[AsyncGlpiClient]:
    """Yield a default in-memory client and close it afterwards."""

    instance = make_client()
    yield instance
    await instance.close()
