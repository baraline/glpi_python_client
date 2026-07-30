"""Unit tests for the ``Dropdowns/Location`` endpoint mixin.

The tests cover search, fetch, create, update, and delete for GLPI
locations, using the shared transport recorders to stub the four
transport helpers without any HTTP plumbing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import PatchLocation, PostLocation
from glpi_python_client._async._testing import (
    FailingTransportRecorder,
    TransportRecorder,
)

# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------


async def test_search_locations_passes_filter(client: Any) -> None:
    """``search_locations`` forwards the RSQL filter through ``filter``."""

    rec = TransportRecorder(get_payload=[{"id": 1, "name": "Paris"}])
    rec.install(client)
    locations = await client.search_locations("name==Paris")
    assert locations[0].id == 1
    assert rec.calls[0]["endpoint"] == "Dropdowns/Location"
    assert rec.calls[0]["params"]["filter"] == "name==Paris"


async def test_get_location_endpoint(client: Any) -> None:
    """``get_location`` hits the per-id endpoint."""

    rec = TransportRecorder(get_payload={"id": 9, "name": "Paris"})
    rec.install(client)
    loc = await client.get_location(9)
    assert loc.id == 9
    assert rec.calls[0]["endpoint"] == "Dropdowns/Location/9"


async def test_update_location(client: Any) -> None:
    """``update_location`` patches the per-id endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    await client.update_location(9, PatchLocation(name="Paris HQ"))
    assert rec.calls[0]["endpoint"] == "Dropdowns/Location/9"


async def test_delete_location_with_force(client: Any) -> None:
    """``delete_location(force=True)`` ships the force flag in the body."""

    rec = TransportRecorder()
    rec.install(client)
    await client.delete_location(9, force=True)
    call = rec.calls[0]
    assert call["method"] == "DELETE"
    assert call["endpoint"] == "Dropdowns/Location/9"
    assert call["json"] == {"force": True}


async def test_create_location_targets_dropdown_endpoint(client: Any) -> None:
    """``create_location`` posts to the dropdown endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    await client.create_location(PostLocation(name="Paris"))
    call = rec.calls[0]
    assert call["endpoint"] == "Dropdowns/Location"


# ---------------------------------------------------------------------------
# Generic error handling (this mixin's share of the shared failure suites)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_location(1),
    ],
)
async def test_get_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every read helper raises on a non-success status."""

    FailingTransportRecorder(404).install(client)
    with pytest.raises(ValueError):
        await call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.update_location(1, PatchLocation(name="x")),
    ],
)
async def test_update_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every update helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        await call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.delete_location(1, force=True),
    ],
)
async def test_delete_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every delete helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        await call(client)
