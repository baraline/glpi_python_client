"""Smoke tests for the custom_schema aggregated views."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from glpi_python_client.models.custom_schema import (
    GlpiTicketContext,
    TicketMarkdownOptions,
)


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


def test_to_markdown_ignores_timeline_position_for_ordering() -> None:
    """Timeline anchoring does not override chronological ordering."""

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
    assert rendered.index("no position late") < rendered.index("left positioned")
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


# ---------------------------------------------------------------------------
# TicketMarkdownOptions - section inclusion
# ---------------------------------------------------------------------------


_FULL_PAYLOAD = {
    "ticket": {
        "id": 1,
        "name": "Test ticket",
        "content": "body text",
        "status": {"id": 2, "name": "Open"},
        "user_recipient": {"id": 3, "name": "Alice"},
        "user_editor": {"id": 4, "name": "Bob"},
        "date_creation": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "date_mod": datetime(2024, 1, 2, tzinfo=timezone.utc),
    },
    "followups": [{"id": 10, "content": "followup body"}],
    "tasks": [{"id": 20, "content": "task body", "duration": 600}],
    "solutions": [{"id": 30, "content": "solution body"}],
    "documents": [{"id": 40, "documents_id": 99, "filepath": "file.txt"}],
}


def test_options_exclude_description() -> None:
    """``include_description=False`` omits the description section."""

    context = GlpiTicketContext.model_validate(_FULL_PAYLOAD)
    rendered = context.to_markdown(TicketMarkdownOptions(include_description=False))
    assert "## Description" not in rendered
    assert "body text" not in rendered


def test_options_exclude_followups() -> None:
    """``include_followups=False`` omits followup entries from the timeline."""

    context = GlpiTicketContext.model_validate(_FULL_PAYLOAD)
    rendered = context.to_markdown(TicketMarkdownOptions(include_followups=False))
    assert "### Followup" not in rendered
    assert "followup body" not in rendered
    assert "### Task #20" in rendered


def test_options_exclude_tasks() -> None:
    """``include_tasks=False`` omits task entries from the timeline."""

    context = GlpiTicketContext.model_validate(_FULL_PAYLOAD)
    rendered = context.to_markdown(TicketMarkdownOptions(include_tasks=False))
    assert "### Task" not in rendered
    assert "task body" not in rendered
    assert "### Followup #10" in rendered


def test_options_exclude_solutions() -> None:
    """``include_solutions=False`` omits solution entries from the timeline."""

    context = GlpiTicketContext.model_validate(_FULL_PAYLOAD)
    rendered = context.to_markdown(TicketMarkdownOptions(include_solutions=False))
    assert "### Solution" not in rendered
    assert "solution body" not in rendered


def test_options_exclude_documents() -> None:
    """``include_documents=False`` omits the documents section."""

    context = GlpiTicketContext.model_validate(_FULL_PAYLOAD)
    rendered = context.to_markdown(TicketMarkdownOptions(include_documents=False))
    assert "## Documents" not in rendered
    assert "file.txt" not in rendered


def test_options_exclude_all_timeline_sections() -> None:
    """Excluding all three timeline types also removes the Timeline heading."""

    context = GlpiTicketContext.model_validate(_FULL_PAYLOAD)
    rendered = context.to_markdown(
        TicketMarkdownOptions(
            include_followups=False,
            include_tasks=False,
            include_solutions=False,
        )
    )
    assert "## Timeline" not in rendered


# ---------------------------------------------------------------------------
# TicketMarkdownOptions - ticket header field visibility
# ---------------------------------------------------------------------------


def test_options_hide_status() -> None:
    """``show_status=False`` removes the status from the ticket subtitle."""

    context = GlpiTicketContext.model_validate(_FULL_PAYLOAD)
    rendered = context.to_markdown(TicketMarkdownOptions(show_status=False))
    assert "Status: Open" not in rendered
    assert "Requester: Alice" in rendered


def test_options_hide_requester() -> None:
    """``show_requester=False`` removes the requester from the ticket subtitle."""

    context = GlpiTicketContext.model_validate(_FULL_PAYLOAD)
    rendered = context.to_markdown(TicketMarkdownOptions(show_requester=False))
    assert "Requester:" not in rendered
    assert "Status: Open" in rendered


def test_options_hide_editor() -> None:
    """``show_editor=False`` removes the editor from the ticket subtitle."""

    context = GlpiTicketContext.model_validate(_FULL_PAYLOAD)
    rendered = context.to_markdown(TicketMarkdownOptions(show_editor=False))
    assert "Last edited by: Bob" not in rendered


def test_options_hide_dates() -> None:
    """``show_dates=False`` removes all date fields from the ticket subtitle."""

    context = GlpiTicketContext.model_validate(_FULL_PAYLOAD)
    rendered = context.to_markdown(TicketMarkdownOptions(show_dates=False))
    assert "Created at:" not in rendered
    assert "Updated at:" not in rendered
    assert "Status: Open" in rendered


# ---------------------------------------------------------------------------
# TicketMarkdownOptions - timeline event field visibility
# ---------------------------------------------------------------------------


def test_options_hide_event_author() -> None:
    """``show_event_author=False`` removes the creator from event subtitles."""

    context = GlpiTicketContext.model_validate(
        {
            "ticket": {"id": 1, "name": "x"},
            "followups": [
                {"id": 5, "content": "note", "user": {"id": 7, "name": "Alice"}}
            ],
        }
    )
    rendered = context.to_markdown(TicketMarkdownOptions(show_event_author=False))
    assert "Created by:" not in rendered


def test_options_hide_event_dates() -> None:
    """``show_event_dates=False`` removes all date fields from event subtitles."""

    context = GlpiTicketContext.model_validate(
        {
            "ticket": {"id": 1, "name": "x"},
            "followups": [
                {
                    "id": 5,
                    "content": "note",
                    "date_creation": datetime(2024, 3, 1, tzinfo=timezone.utc),
                }
            ],
        }
    )
    rendered = context.to_markdown(TicketMarkdownOptions(show_event_dates=False))
    assert "Created at:" not in rendered


def test_options_hide_duration() -> None:
    """``show_duration=False`` removes the duration from task subtitles."""

    context = GlpiTicketContext.model_validate(
        {
            "ticket": {"id": 1, "name": "x"},
            "tasks": [{"id": 9, "content": "work", "duration": 1800}],
        }
    )
    rendered = context.to_markdown(TicketMarkdownOptions(show_duration=False))
    assert "Duration:" not in rendered
    assert "work" in rendered


def test_options_default_reproduces_original_output() -> None:
    """A bare ``to_markdown()`` call and an explicit default options call are equal."""

    context = GlpiTicketContext.model_validate(_FULL_PAYLOAD)
    assert context.to_markdown() == context.to_markdown(TicketMarkdownOptions())
