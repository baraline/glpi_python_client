from __future__ import annotations

from typing import Any

from glpi_python_client.content.records.parsers.timeline import (
    _glpi_followup_record,
    _glpi_task_record,
)


def test_followup_record_extracts_and_strips_document_references(
    sample_followup_record: dict[str, Any],
) -> None:
    followup = _glpi_followup_record(sample_followup_record)

    assert followup.followup_id == "12"
    assert followup.author is not None
    assert followup.author.user_id == "5"
    assert followup.is_private is True
    assert followup.attachment_document_ids == ("45", "46")
    assert followup.content is not None
    assert "document.send.php" not in followup.content
    assert "Hello" in followup.content


def test_task_record_parses_duration_user_and_extra_payload() -> None:
    task = _glpi_task_record(
        {
            "id": 14,
            "tickets_id": 321,
            "users_id": 7,
            "user": {"id": 7, "name": "jdoe"},
            "user_editor": {"id": 8, "name": "manager"},
            "actiontime": "3600",
            "date": "2026-01-15 10:30:00",
            "content": "<p>Worked on <strong>analysis</strong></p>",
            "entities_id": 12,
            "source": "search",
        }
    )

    assert task.task_id == "14"
    assert task.ticket_id == "321"
    assert task.user_id == "7"
    assert task.user is not None
    assert task.user.name == "jdoe"
    assert task.editor is not None
    assert task.editor.user_id == "8"
    assert task.duration == 3600
    assert task.content == "Worked on **analysis**"
    assert task.entity == 12
    assert task.extra_payload == {"source": "search"}
