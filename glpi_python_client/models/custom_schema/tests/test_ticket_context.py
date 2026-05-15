"""Smoke tests for the custom_schema aggregated views."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from glpi_python_client.models.custom_schema import GlpiTicketContext


def test_ticket_context_requires_ticket() -> None:
    """``GlpiTicketContext`` requires the ``ticket`` field to be present."""

    with pytest.raises(ValidationError):
        GlpiTicketContext.model_validate({})


def test_ticket_context_default_collections_empty() -> None:
    """``GlpiTicketContext`` defaults timeline collections to empty lists."""

    context = GlpiTicketContext.model_validate({"ticket": {"id": 1, "name": "x"}})
    assert context.tasks == []
    assert context.followups == []
    assert context.solutions == []
    assert context.documents == []


def test_ticket_context_accepts_timeline_records() -> None:
    """``GlpiTicketContext`` validates nested timeline payloads."""

    payload = {
        "ticket": {"id": 1, "name": "x"},
        "tasks": [{"id": 11, "content": "<p>do</p>"}],
        "followups": [{"id": 12, "content": "<p>note</p>"}],
        "solutions": [{"id": 13, "content": "<p>fix</p>"}],
        "documents": [{"id": 14, "documents_id": 99}],
    }
    context = GlpiTicketContext.model_validate(payload)
    assert context.tasks[0].id == 11
    assert context.documents[0].documents_id == 99


def test_to_markdown_renders_header_and_status() -> None:
    """``to_markdown`` includes the ticket id, name, status and content."""

    context = GlpiTicketContext.model_validate(
        {
            "ticket": {
                "id": 42,
                "name": "Printer broken",
                "content": "Cannot print",
                "status": {"id": 2, "name": "Processing (assigned)"},
            }
        }
    )
    rendered = context.to_markdown()
    assert rendered.startswith("# Ticket #42 \u2014 Printer broken")
    assert "> Status: Processing (assigned)" in rendered
    assert "## Description" in rendered
    assert "Cannot print" in rendered


def test_to_markdown_renders_ticket_subtitle_metadata() -> None:
    """The main ticket subtitle includes requester, editor, and timestamps."""

    context = GlpiTicketContext.model_validate(
        {
            "ticket": {
                "id": 42,
                "name": "Printer broken",
                "user_recipient": {"id": 7, "name": "Alice"},
                "user_editor": {"id": 8, "name": "Bob"},
                "date_creation": datetime(2024, 1, 1, 9, 30, tzinfo=timezone.utc),
                "date_mod": datetime(2024, 1, 2, 11, 45, tzinfo=timezone.utc),
            }
        }
    )

    rendered = context.to_markdown()

    assert "Requester: Alice" in rendered
    assert "Last edited by: Bob" in rendered
    assert "Created at: 2024-01-01T09:30:00+00:00" in rendered
    assert "Updated at: 2024-01-02T11:45:00+00:00" in rendered


def test_to_markdown_orders_events_by_creation_when_no_position() -> None:
    """Events without ``timeline_position`` are ordered by creation date."""

    context = GlpiTicketContext.model_validate(
        {
            "ticket": {"id": 1, "name": "x"},
            "followups": [
                {
                    "id": 2,
                    "content": "second note",
                    "date_creation": datetime(2024, 1, 2, tzinfo=timezone.utc),
                },
                {
                    "id": 1,
                    "content": "first note",
                    "date_creation": datetime(2024, 1, 1, tzinfo=timezone.utc),
                },
            ],
        }
    )
    rendered = context.to_markdown()
    assert rendered.index("first note") < rendered.index("second note")


def test_to_markdown_prefers_timeline_position_over_creation() -> None:
    """Events carrying a positive ``timeline_position`` come first in order."""

    context = GlpiTicketContext.model_validate(
        {
            "ticket": {"id": 1, "name": "x"},
            "followups": [
                {
                    "id": 1,
                    "content": "no position late",
                    "date_creation": datetime(2024, 1, 5, tzinfo=timezone.utc),
                },
            ],
            "tasks": [
                {
                    "id": 2,
                    "content": "left positioned",
                    "timeline_position": 1,
                    "date_creation": datetime(2024, 1, 10, tzinfo=timezone.utc),
                },
            ],
        }
    )
    rendered = context.to_markdown()
    assert rendered.index("left positioned") < rendered.index("no position late")
    assert "## Timeline" in rendered
    assert "### Task #2" in rendered
    assert "### Followup #1" in rendered


def test_to_markdown_renders_solution_and_documents() -> None:
    """Solutions and document links are rendered with their dedicated sections."""

    context = GlpiTicketContext.model_validate(
        {
            "ticket": {"id": 7, "name": "Reset"},
            "solutions": [{"id": 4, "content": "All fixed"}],
            "documents": [
                {"id": 11, "documents_id": 99, "filepath": "logs/run.txt"},
                {"id": 12, "documents_id": 100},
            ],
        }
    )
    rendered = context.to_markdown()
    assert "### Solution #4" in rendered
    assert "All fixed" in rendered
    assert "## Documents" in rendered
    assert "- logs/run.txt" in rendered
    assert "- document #100" in rendered


def test_to_markdown_handles_empty_timeline() -> None:
    """A ticket with no events still produces a valid Markdown header."""

    context = GlpiTicketContext.model_validate({"ticket": {"id": 3, "name": "Quiet"}})
    rendered = context.to_markdown()
    assert rendered == "# Ticket #3 \u2014 Quiet"


def test_to_markdown_renders_task_duration() -> None:
    """Tasks expose their ``duration`` field in seconds."""

    context = GlpiTicketContext.model_validate(
        {
            "ticket": {"id": 1, "name": "x"},
            "tasks": [{"id": 9, "content": "work", "duration": 1800}],
        }
    )
    rendered = context.to_markdown()
    assert "> Duration: 1800s" in rendered


def test_to_markdown_renders_event_creator_editor_and_timestamps() -> None:
    """Timeline subtitles include author, editor, and timestamp metadata."""

    context = GlpiTicketContext.model_validate(
        {
            "ticket": {"id": 1, "name": "x"},
            "followups": [
                {
                    "id": 12,
                    "content": "note",
                    "user": {"id": 7, "name": "Alice"},
                    "user_editor": {"id": 8, "name": "Bob"},
                    "date_creation": datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc),
                    "date_mod": datetime(2024, 1, 2, 10, 5, tzinfo=timezone.utc),
                }
            ],
        }
    )

    rendered = context.to_markdown()

    assert "### Followup #12" in rendered
    assert "Created by: Alice" in rendered
    assert "Last edited by: Bob" in rendered
    assert "Created at: 2024-01-02T10:00:00+00:00" in rendered
    assert "Updated at: 2024-01-02T10:05:00+00:00" in rendered
