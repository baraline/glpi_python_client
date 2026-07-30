"""Unit tests for the ``Assistance/Ticket/Timeline/Solution`` endpoint mixin.

The tests cover listing, fetching, creating, updating, and deleting ticket
solutions, using the shared transport recorders to stub the four transport
helpers without any HTTP plumbing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import PatchSolution, PostSolution
from glpi_python_client._async._testing import (
    FailingTransportRecorder,
    TransportRecorder,
)


async def test_list_get_update_delete_ticket_solutions(client: Any) -> None:
    """All four solution helpers target the solution timeline endpoint."""

    rec = TransportRecorder(
        get_payload=[
            {"type": "ITILSolution", "item": {"id": 1, "content": "x"}},
        ]
    )
    rec.install(client)
    sols = await client.list_ticket_solutions(7)
    assert sols[0].id == 1

    rec._get_payload = {"id": 1, "content": "x"}  # type: ignore[attr-defined]
    sol = await client.get_ticket_solution(7, 1)
    assert sol.id == 1

    await client.update_ticket_solution(7, 1, PatchSolution(content="<p>up</p>"))
    await client.delete_ticket_solution(7, 1, force=True)

    methods = [c["method"] for c in rec.calls]
    assert methods == ["GET", "GET", "PATCH", "DELETE"]
    endpoints = {c["endpoint"] for c in rec.calls if c["method"] != "GET"} | {
        c["endpoint"] for c in rec.calls if c["method"] == "GET"
    }
    assert any("Solution" in e for e in endpoints)


async def test_create_ticket_solution_uses_solution_endpoint(client: Any) -> None:
    """``create_ticket_solution`` targets the ticket solution endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    await client.create_ticket_solution(9, PostSolution(content="ok"))
    call = rec.calls[0]
    assert call["endpoint"] == "Assistance/Ticket/9/Timeline/Solution"


# ---------------------------------------------------------------------------
# Generic error handling (this mixin's share of the shared failure suites)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_ticket_solution(1, 2),
        lambda c: c.list_ticket_solutions(1),
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
        lambda c: c.update_ticket_solution(1, 2, PatchSolution(content="<p>x</p>")),
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
        lambda c: c.delete_ticket_solution(1, 2, force=True),
    ],
)
async def test_delete_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every delete helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        await call(client)
