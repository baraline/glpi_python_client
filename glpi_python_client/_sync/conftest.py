"""Fixtures shared by every unit test in this tree.

Generated into the sync tree alongside the modules it serves, so both
surfaces get a fixture that builds the client they actually test.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from glpi_python_client import GlpiClient
from glpi_python_client._sync._testing import make_client


@pytest.fixture
def client() -> Iterator[GlpiClient]:
    """Yield a default in-memory client and close it afterwards."""

    instance = make_client()
    yield instance
    instance.close()
