from __future__ import annotations

from typing import Any

from glpi_python_client.content.records.parsers.timeline import _glpi_followup_record


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
