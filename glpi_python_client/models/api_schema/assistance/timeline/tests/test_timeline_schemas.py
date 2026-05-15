"""Smoke tests for the assistance.timeline api_schema models."""

from __future__ import annotations

from glpi_python_client.models.api_schema.assistance.timeline import (
    DeleteFollowup,
    DeleteSolution,
    DeleteTicketTask,
    DeleteTimelineDocument,
    GetFollowup,
    GetSolution,
    GetTicketTask,
    GetTimelineDocument,
    PatchFollowup,
    PatchSolution,
    PatchTicketTask,
    PatchTimelineDocument,
    PostFollowup,
    PostSolution,
    PostTicketTask,
    PostTimelineDocument,
)
from glpi_python_client.models.api_schema.enums import (
    GlpiSolutionStatus,
    GlpiTaskState,
    GlpiTimelinePosition,
)


def test_get_followup_full_payload() -> None:
    """``GetFollowup`` accepts every contract field of the ``Followup`` schema."""

    payload = {
        "id": 1,
        "itemtype": "Ticket",
        "items_id": 99,
        "content": "<p>text</p>",
        "is_private": False,
        "user": {"id": 2, "name": "bob"},
        "user_editor": {"id": 3, "name": "carol"},
        "request_type": {"id": 1, "name": "Helpdesk"},
        "date": "2024-01-02T03:04:05",
        "date_creation": "2024-01-02T03:04:05",
        "date_mod": "2024-01-02T03:04:05",
        "timeline_position": 1,
        "source_item_id": 0,
        "source_of_item_id": 0,
    }
    followup = GetFollowup.model_validate(payload)
    assert followup.timeline_position is GlpiTimelinePosition.LEFT


def test_post_followup_excludes_read_only_id() -> None:
    """Read-only ``id`` flows into ``extra_payload`` for server-side rejection."""

    followup = PostFollowup.model_validate({"id": 1, "content": "x"})
    assert followup.extra_payload == {"id": 1}
    PatchFollowup.model_validate({"content": "y", "is_private": True})
    assert DeleteFollowup().force is None


def test_get_task_full_payload() -> None:
    """``GetTicketTask`` accepts every contract field of the schema."""

    payload = {
        "id": 11,
        "uuid": "00000000-0000-4000-8000-000000000000",
        "content": "<p>do</p>",
        "is_private": True,
        "user": {"id": 1, "name": "alice"},
        "user_editor": {"id": 2, "name": "bob"},
        "user_tech": {"id": 3, "name": "carol"},
        "group_tech": {"id": 4, "name": "infra"},
        "duration": 3600,
        "state": 1,
        "category": {"id": 5, "name": "ops"},
        "timeline_position": 2,
        "tickets_id": 99,
        "source_item_id": 0,
        "source_of_item_id": 0,
    }
    task = GetTicketTask.model_validate(payload)
    assert task.state is GlpiTaskState.TODO
    assert task.timeline_position is GlpiTimelinePosition.RIGHT


def test_post_task_excludes_read_only_fields() -> None:
    """Read-only ``id``/``uuid`` into ``extra_payload`` for server-side rejection."""

    for forbidden in ("id", "uuid"):
        task = PostTicketTask.model_validate({forbidden: "x", "content": "y"})
        assert task.extra_payload == {forbidden: "x"}
    PatchTicketTask.model_validate({"state": 2})
    assert DeleteTicketTask().force is None


def test_get_solution_full_payload() -> None:
    """``GetSolution`` accepts every contract field of the schema."""

    payload = {
        "id": 5,
        "itemtype": "Ticket",
        "items_id": 99,
        "type": {"id": 1, "name": "Workaround"},
        "content": "<p>fix</p>",
        "user": {"id": 1, "name": "alice"},
        "user_editor": {"id": 2, "name": "bob"},
        "approver": {"id": 3, "name": "carol"},
        "status": 3,
        "approval_followup": {"id": 7, "name": "approval"},
        "date_creation": "2024-01-02T03:04:05",
        "date_mod": "2024-01-02T03:04:05",
        "date_approval": "2024-01-03T03:04:05",
    }
    solution = GetSolution.model_validate(payload)
    assert solution.status is GlpiSolutionStatus.ACCEPTED


def test_post_solution_excludes_read_only_id() -> None:
    """Read-only ``id`` flows into ``extra_payload`` for server-side rejection."""

    solution = PostSolution.model_validate({"id": 1, "content": "x"})
    assert solution.extra_payload == {"id": 1}
    PatchSolution.model_validate({"content": "y"})
    assert DeleteSolution().force is None


def test_timeline_document_round_trip() -> None:
    """The timeline document models honour their RO-only contract layout."""

    payload = {
        "id": 1,
        "itemtype": "Ticket",
        "items_id": 99,
        "documents_id": 5,
        "filepath": "PDF/x.pdf",
        "timeline_position": 0,
    }
    link = GetTimelineDocument.model_validate(payload)
    assert link.documents_id == 5

    for forbidden in ("id", "itemtype", "items_id", "documents_id", "filepath"):
        link_extras = PostTimelineDocument.model_validate({forbidden: "x"})
        assert link_extras.extra_payload == {forbidden: "x"}

    PatchTimelineDocument.model_validate({"timeline_position": 1})
    assert DeleteTimelineDocument().force is None
