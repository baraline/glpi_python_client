"""Pytest fixtures backed by shared glpi_python_client test utilities.

These fixtures provide a reusable client factory for unit tests while
delegating the concrete data construction to the shared testing utilities.

**Requires pytest**, which is deliberately *not* a runtime dependency of
this package -- it is declared in the ``dev`` extra. This module ships so
downstream test suites can register it, and any suite doing so already has
pytest installed. Importing it from application code raises
``ModuleNotFoundError``; import :mod:`glpi_python_client.testing.utils`
instead, which has no test-framework dependency. Register the fixtures
with ``pytest_plugins = ("glpi_python_client.testing.fixtures",)`` in your
own ``conftest.py``.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from glpi_python_client import GlpiClient
from glpi_python_client.testing.utils import make_client


@pytest.fixture
def client_factory() -> Callable[..., GlpiClient]:
    """Return the reusable synchronous GLPI client factory fixture.

    Tests can call the returned factory with overrides to create focused
    client instances without duplicating the base configuration shared by
    the rest of the unit-test suite.
    """

    return make_client
