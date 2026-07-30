"""Unit tests for the ``Assistance/Ticket/Timeline/Task`` endpoint mixin.

The tests cover listing, fetching, creating, updating, and deleting ticket
tasks, using the shared transport recorders to stub the four transport
helpers without any HTTP plumbing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import PatchTicketTask, PostTicketTask
from glpi_python_client._sync._testing import (
    FailingTransportRecorder,
    TransportRecorder,
)


def test_list_get_update_delete_ticket_tasks(client: Any) -> None:
    """All four task helpers target the task timeline endpoint."""

    rec = TransportRecorder(
        get_payload=[
            {"type": "TicketTask", "item": {"id": 1, "content": "x"}},
        ]
    )
    rec.install(client)
    tasks = client.list_ticket_tasks(7)
    assert tasks[0].id == 1
    assert rec.calls[0]["endpoint"] == "Assistance/Ticket/7/Timeline/Task"

    rec.calls.clear()
    rec._get_payload = {"id": 1, "content": "x"}  # type: ignore[attr-defined]
    task = client.get_ticket_task(7, 1)
    assert task.id == 1

    client.update_ticket_task(7, 1, PatchTicketTask(content="<p>up</p>"))
    client.delete_ticket_task(7, 1, force=True)

    endpoints = [c["endpoint"] for c in rec.calls]
    assert endpoints == [
        "Assistance/Ticket/7/Timeline/Task/1",
        "Assistance/Ticket/7/Timeline/Task/1",
        "Assistance/Ticket/7/Timeline/Task/1",
    ]


def test_create_ticket_task_uses_task_endpoint(client: Any) -> None:
    """``create_ticket_task`` targets the ticket task timeline endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    client.create_ticket_task(8, PostTicketTask(content="task", duration=120))
    call = rec.calls[0]
    assert call["endpoint"] == "Assistance/Ticket/8/Timeline/Task"
    assert call["json"] == {"content": "<p>task</p>", "duration": 120}


# ---------------------------------------------------------------------------
# Generic error handling (this mixin's share of the shared failure suites)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_ticket_task(1, 2),
        lambda c: c.list_ticket_tasks(1),
    ],
)
def test_get_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every read helper raises on a non-success status."""

    FailingTransportRecorder(404).install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.update_ticket_task(1, 2, PatchTicketTask(content="<p>x</p>")),
    ],
)
def test_update_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every update helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.delete_ticket_task(1, 2, force=True),
    ],
)
def test_delete_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every delete helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        call(client)
