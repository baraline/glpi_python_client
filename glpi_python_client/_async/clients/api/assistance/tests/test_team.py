"""Unit tests for the ``Assistance/Ticket/TeamMember`` endpoint mixin.

The tests cover listing, adding, and removing ticket team members, using
the shared transport recorders to stub the four transport helpers without
any HTTP plumbing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import PostTeamMember
from glpi_python_client._async._testing import (
    FailingTransportRecorder,
    TransportRecorder,
)


async def test_list_ticket_team_members_endpoint(client: Any) -> None:
    """``list_ticket_team_members`` hits the team-member endpoint."""

    rec = TransportRecorder(get_payload=[{"id": 1, "type": "User", "role": "assigned"}])
    rec.install(client)
    members = await client.list_ticket_team_members(7)
    assert members[0].id == 1
    assert rec.calls[0]["endpoint"] == "Assistance/Ticket/7/TeamMember"


async def test_add_ticket_team_member_targets_team_endpoint(client: Any) -> None:
    """``add_ticket_team_member`` posts to the ticket team-member endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    await client.add_ticket_team_member(
        11, PostTeamMember(type="User", id=42, role="assigned")
    )

    call = rec.calls[0]
    assert call["endpoint"] == "Assistance/Ticket/11/TeamMember"
    assert call["json"] == {"type": "User", "id": 42, "role": "assigned"}


async def test_remove_ticket_team_member_uses_delete(client: Any) -> None:
    """``remove_ticket_team_member`` issues DELETE with the member body."""

    rec = TransportRecorder()
    rec.install(client)
    await client.remove_ticket_team_member(
        7, PostTeamMember(type="User", id=42, role="assigned")
    )

    call = rec.calls[0]
    assert call["method"] == "DELETE"
    assert call["endpoint"] == "Assistance/Ticket/7/TeamMember"
    assert call["json"] == {"type": "User", "id": 42, "role": "assigned"}


# ---------------------------------------------------------------------------
# Generic error handling (this mixin's share of the shared failure suites)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.list_ticket_team_members(1),
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
        lambda c: c.remove_ticket_team_member(
            1, PostTeamMember(type="User", id=2, role="assigned")
        ),
    ],
)
async def test_delete_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every delete helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        await call(client)
