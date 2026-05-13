from __future__ import annotations

from typing import Any

from glpi_python_client.content.records.parsers.tickets import (
    _filter_visible_ticket_batch,
    _glpi_ticket_record,
)


def test_ticket_record_normalizes_nested_fields(
    sample_ticket_record: dict[str, Any],
) -> None:
    ticket = _glpi_ticket_record(sample_ticket_record)

    assert ticket.id == "123"
    assert ticket.status == {"id": 2, "name": "Processing"}
    assert ticket.entity == {"id": 7, "name": "Root"}
    assert ticket.location == {"id": 8, "name": "Paris"}
    assert ticket.content == "Body with **formatting**"
    assert ticket.user_recipient is not None
    assert ticket.user_recipient.user_id == "9"


def test_filter_visible_ticket_batch_removes_deleted_records() -> None:
    visible, deleted_count = _filter_visible_ticket_batch(
        [
            {"id": 1, "is_deleted": 0},
            {"id": 2, "is_deleted": "true"},
            {"id": 3, "is_deleted": False},
        ]
    )

    assert [ticket["id"] for ticket in visible] == [1, 3]
    assert deleted_count == 1
