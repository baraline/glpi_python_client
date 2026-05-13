"""GLPI ticket record parsing helpers.

This module converts raw ticket payloads and search batches into the package's
typed ``GlpiTicket`` model while handling deleted-ticket filtering.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from glpi_python_client.content.conversion import GlpiContentConverter
from glpi_python_client.content.records.core.references import (
    _glpi_id_reference,
    _glpi_reference,
    _glpi_text_reference,
    _glpi_ticket_user_payload,
)
from glpi_python_client.content.records.core.scalars import (
    _optional_int,
    _optional_text,
    _parse_glpi_datetime,
)
from glpi_python_client.models import GlpiTicket


def _is_deleted_ticket(record: dict[str, Any]) -> bool:
    """Return whether one raw GLPI ticket payload represents a deleted ticket.

    GLPI may encode this flag as a boolean, numeric sentinel, or text value, so
    the helper accepts all of those shapes.
    """

    value = record.get("is_deleted")
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes"}
    return False


def _filter_visible_ticket_batch(batch: object) -> tuple[list[dict[str, Any]], int]:
    """Filter deleted tickets out of one GLPI search batch.

    The function returns both the visible ticket payloads and the count removed
    so callers can log how many deleted records were excluded.
    """

    if not isinstance(batch, list):
        return [], 0
    normalized_batch = [dict(ticket) for ticket in batch if isinstance(ticket, dict)]
    visible_batch = [
        ticket for ticket in normalized_batch if not _is_deleted_ticket(ticket)
    ]
    return visible_batch, len(normalized_batch) - len(visible_batch)


def _glpi_ticket_record(raw_ticket: dict[str, Any]) -> GlpiTicket:
    """Build a rich ``GlpiTicket`` object from one raw ticket payload.

    The parser normalizes content, references, timestamps, and embedded user
    fields while preserving the payload keys that map directly to the public
    ticket model.
    """

    fields = dict(raw_ticket)
    status = fields.pop("status", None)
    ticket_id = _optional_text(fields.pop("id", None))
    name = _optional_text(fields.pop("name", None))
    content = str(fields.pop("content", "") or "")
    if ticket_id is None:
        raise ValueError("GLPI ticket payload did not include an ID")
    external_id = _optional_text(fields.get("external_id"))
    return GlpiTicket(
        id=ticket_id,
        name=name,
        content=GlpiContentConverter.from_transport(content),
        status=_glpi_id_reference(status),
        urgency=_optional_int(fields.get("urgency")),
        impact=_optional_int(fields.get("impact")),
        priority=_optional_int(fields.get("priority")),
        type=_optional_int(fields.get("type")),
        external_id=external_id,
        category=_glpi_id_reference(fields.get("category")),
        entity=_glpi_id_reference(fields.get("entity")),
        location=_glpi_reference(fields.get("location")),
        request_type=_glpi_text_reference(fields.get("request_type")),
        date_creation=_parse_glpi_datetime(fields.get("date_creation")),
        date_mod=_parse_glpi_datetime(fields.get("date_mod"))
        or datetime.now().astimezone(),
        date_close=_parse_glpi_datetime(fields.get("date_close")),
        user_recipient=_glpi_ticket_user_payload(fields.get("user_recipient")),
        user_editor=_glpi_ticket_user_payload(fields.get("user_editor")),
    )
