"""Unit tests for the ``Assistance/Ticket/Timeline/Followup`` endpoint mixin.

The tests cover listing, fetching, creating, updating, and deleting ticket
followups, using the shared transport recorders to stub the four transport
helpers without any HTTP plumbing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import PatchFollowup, PostFollowup
from glpi_python_client._sync._testing import (
    FailingTransportRecorder,
    TransportRecorder,
)


def test_list_ticket_followups_unwraps_envelope(client: Any) -> None:
    """Live envelope ``{"type":..,"item":..}`` entries are unwrapped."""

    rec = TransportRecorder(
        get_payload=[
            {"type": "ITILFollowup", "item": {"id": 11, "content": "hi"}},
            {"id": 12, "content": "bye"},
        ]
    )
    rec.install(client)
    items = client.list_ticket_followups(7)
    assert [i.id for i in items] == [11, 12]
    assert rec.calls[0]["endpoint"] == "Assistance/Ticket/7/Timeline/Followup"


def test_get_ticket_followup_endpoint(client: Any) -> None:
    """``get_ticket_followup`` hits the per-id endpoint."""

    rec = TransportRecorder(get_payload={"id": 11, "content": "x"})
    rec.install(client)
    followup = client.get_ticket_followup(7, 11)
    assert followup.id == 11
    assert rec.calls[0]["endpoint"] == "Assistance/Ticket/7/Timeline/Followup/11"


def test_update_ticket_followup_patch(client: Any) -> None:
    """``update_ticket_followup`` patches the per-id endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    client.update_ticket_followup(7, 11, PatchFollowup(content="<p>up</p>"))
    assert rec.calls[0]["endpoint"] == "Assistance/Ticket/7/Timeline/Followup/11"


def test_delete_ticket_followup_force(client: Any) -> None:
    """``delete_ticket_followup(force=True)`` adds the body."""

    rec = TransportRecorder()
    rec.install(client)
    client.delete_ticket_followup(7, 11, force=True)
    assert rec.calls[0]["json"] == {"force": True}


def test_create_ticket_followup_targets_timeline_endpoint(client: Any) -> None:
    """``create_ticket_followup`` posts to the ticket timeline endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    client.create_ticket_followup(7, PostFollowup(content="<p>hi</p>"))
    call = rec.calls[0]
    assert call["endpoint"] == "Assistance/Ticket/7/Timeline/Followup"
    assert call["json"] == {"content": "<p>hi</p>"}


# ---------------------------------------------------------------------------
# Generic error handling (this mixin's share of the shared failure suites)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_ticket_followup(1, 2),
        lambda c: c.list_ticket_followups(1),
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
        lambda c: c.update_ticket_followup(1, 2, PatchFollowup(content="<p>x</p>")),
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
        lambda c: c.delete_ticket_followup(1, 2, force=True),
    ],
)
def test_delete_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every delete helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        call(client)
