from __future__ import annotations

from glpi_python_client import GlpiTicket


def test_ticket_payload_uses_glpi_high_level_shapes() -> None:
    ticket = GlpiTicket(
        name="Printer issue",
        content="Cannot print from accounting",
        status=2,
        urgency=3,
        impact=4,
        priority=5,
        type=1,
        category=10,
        location="12",
    )

    payload = ticket.to_api_payload(entity_id=7, include_entity=True)

    assert payload == {
        "name": "Printer issue",
        "content": "<p>Cannot print from accounting</p>",
        "status": {"id": 2},
        "urgency": 3,
        "impact": 4,
        "priority": 5,
        "type": 1,
        "category": {"id": 10},
        "location": {"id": "12"},
        "entity": {"id": 7},
    }


def test_ticket_payload_field_mask_accepts_model_field_names() -> None:
    ticket = GlpiTicket(name="Updated", status=3, priority=4)

    payload = ticket.to_api_payload(field_mask=("name", "status"))

    assert payload == {"name": "Updated", "status": {"id": 3}}


def test_ticket_payload_merges_public_extra_payload() -> None:
    ticket = GlpiTicket(
        name="Access badge reader offline",
        extra_payload={
            "_room_code": "PAR-3F-12",
            "_asset_tag": "BADGE-READER-044",
            "_ignored": None,
        },
    )

    payload = ticket.to_api_payload()

    assert payload == {
        "name": "Access badge reader offline",
        "_room_code": "PAR-3F-12",
        "_asset_tag": "BADGE-READER-044",
    }
