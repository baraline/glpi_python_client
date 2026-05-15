"""Smoke tests for the assistance api_schema ticket and team-member models."""

from __future__ import annotations

from glpi_python_client.models.api_schema.assistance import (
    DeleteTicket,
    GetTeamMember,
    GetTicket,
    PatchTeamMember,
    PatchTicket,
    PostTeamMember,
    PostTicket,
)
from glpi_python_client.models.api_schema.enums import (
    GlpiPriority,
    GlpiTicketType,
)


def test_get_ticket_validates_rich_payload() -> None:
    """``GetTicket`` accepts a representative GLPI ticket response payload."""

    payload = {
        "id": 1234,
        "name": "Crash",
        "content": "<p>boom</p>",
        "user_recipient": {"id": 1, "name": "alice"},
        "user_editor": {"id": 2, "name": "bob"},
        "is_deleted": False,
        "category": {"id": 5, "name": "Bug"},
        "location": {"id": 7, "name": "HQ"},
        "urgency": 3,
        "impact": 4,
        "priority": 4,
        "actiontime": 0,
        "type": 1,
        "external_id": "EXT-1",
        "request_type": {"id": 1, "name": "Helpdesk"},
        "status": {"id": 2, "name": "Assigned"},
        "entity": {"id": 0, "name": "root", "completename": "root"},
        "team": [{"id": 1, "name": "alice", "type": "User", "role": "requester"}],
    }
    ticket = GetTicket.model_validate(payload)
    assert ticket.urgency is GlpiPriority.MEDIUM
    assert ticket.type is GlpiTicketType.INCIDENT
    assert ticket.team is not None
    assert ticket.team[0].role == "requester"


def test_post_ticket_excludes_read_only_fields() -> None:
    """Read-only contract fields are captured in ``extra_payload``.

    The model no longer rejects undeclared fields; the GLPI server is the
    authoritative validator and the helper merely funnels unknown keys into
    ``extra_payload`` so callers (and tests) can introspect what would be
    forwarded.
    """

    forbidden_fields = (
        "id",
        "actiontime",
        "begin_waiting_date",
        "waiting_duration",
        "resolution_duration",
        "close_duration",
        "resolution_date",
        "take_into_account_date",
        "take_into_account_duration",
        "sla_waiting_duration",
        "ola_waiting_duration",
        "ola_ttr_begin_date",
        "ola_tto_begin_date",
        "internal_resolution_date",
        "internal_take_into_account_date",
        "user_recipient",
        "user_editor",
        "team",
        "status",
    )
    for field in forbidden_fields:
        ticket = PostTicket.model_validate({"name": "x", field: 0})
        assert ticket.extra_payload == {field: 0}


def test_patch_ticket_partial_body() -> None:
    """``PatchTicket`` accepts a partial body."""

    PatchTicket.model_validate({"name": "renamed", "priority": 5})


def test_delete_ticket_default() -> None:
    """``DeleteTicket`` exposes ``force`` as optional."""

    assert DeleteTicket().force is None


def test_team_member_round_trip() -> None:
    """``GetTeamMember``/``PostTeamMember``/``PatchTeamMember`` mirror the contract."""

    payload = {"id": 10, "name": "alice", "type": "User", "role": "assigned"}
    member = GetTeamMember.model_validate(payload)
    assert member.role == "assigned"

    PostTeamMember.model_validate({"id": 10, "type": "User", "role": "assigned"})
    PatchTeamMember.model_validate({"role": "observer"})

    extras = PostTeamMember.model_validate({"id": 10, "name": "alice", "role": "x"})
    assert extras.extra_payload == {"name": "alice"}
