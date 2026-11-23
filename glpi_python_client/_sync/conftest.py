"""Fixtures shared by every unit test in this tree.

Generated into the sync tree alongside the modules it serves, so both
surfaces get a fixture that builds the client they actually test.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from glpi_python_client import GlpiClient
from glpi_python_client._sync import _retry
from glpi_python_client._sync._testing import make_client


@pytest.fixture(autouse=True)
def _no_retry_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop the default 3 s pause between retry attempts so tests stay instant."""

    monkeypatch.setattr(_retry, "DEFAULT_RETRY_WAIT_SECONDS", 0.0)


@pytest.fixture
def client() -> Iterator[GlpiClient]:
    """Yield a default in-memory client and close it afterwards."""

    instance = make_client()
    yield instance
    instance.close()
