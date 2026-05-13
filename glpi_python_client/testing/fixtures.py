"""Pytest fixtures backed by shared glpi_python_client test utilities.

These fixtures provide common sample clients and payloads for unit tests while
delegating the concrete data construction to the shared testing utilities.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import GlpiClient
from glpi_python_client.testing.utils import (
    make_client,
    make_followup_record,
    make_ticket_record,
)


@pytest.fixture
def client_factory() -> Callable[..., GlpiClient]:
    """Return the reusable GLPI client factory fixture.

    Tests can call the returned factory with overrides to create focused client
    instances without duplicating base configuration.
    """

    return make_client


@pytest.fixture
def sample_followup_record() -> dict[str, Any]:
    """Return a representative raw GLPI followup payload fixture.

    The payload mirrors the structure expected by the content parsing tests and
    can be overridden in higher-level helpers when needed.
    """

    return make_followup_record()


@pytest.fixture
def sample_ticket_record() -> dict[str, Any]:
    """Return a representative raw GLPI ticket payload fixture.

    The payload captures the common ticket fields exercised by the parsing and
    client tests.
    """

    return make_ticket_record()
