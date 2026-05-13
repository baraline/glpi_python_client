"""Compatibility exports for GLPI record parsing helpers.

The real parsing implementation is split between ``core`` shared helpers and
``parsers`` for model-specific payload conversion. This package preserves the
older aggregate import path for internal callers.
"""

from __future__ import annotations

from glpi_python_client.content.records.core.document_links import (
    _glpi_document_id_from_url,
    _glpi_followup_attachment_document_ids,
    _strip_glpi_document_references,
)
from glpi_python_client.content.records.core.normalization import (
    _normalize_ticket_record,
    _normalize_timeline_records,
    _unwrap_timeline_item,
)
from glpi_python_client.content.records.core.references import (
    _glpi_id_reference,
    _glpi_id_value,
    _glpi_reference,
    _glpi_text_reference,
    _glpi_ticket_user_payload,
)
from glpi_python_client.content.records.core.scalars import (
    _coerce_bool,
    _first_int,
    _optional_int,
    _optional_text,
    _parse_glpi_datetime,
)
from glpi_python_client.content.records.parsers.directory import (
    _glpi_location_record,
    _glpi_user_record,
)
from glpi_python_client.content.records.parsers.documents import _glpi_document_record
from glpi_python_client.content.records.parsers.team import (
    _glpi_team_member_record,
    _resolve_glpi_member_type,
)
from glpi_python_client.content.records.parsers.tickets import (
    _filter_visible_ticket_batch,
    _glpi_ticket_record,
    _is_deleted_ticket,
)
from glpi_python_client.content.records.parsers.timeline import (
    _glpi_author_id,
    _glpi_followup_record,
    _glpi_solution_record,
    _glpi_task_record,
)

__all__ = [
    "_coerce_bool",
    "_filter_visible_ticket_batch",
    "_first_int",
    "_glpi_author_id",
    "_glpi_document_id_from_url",
    "_glpi_document_record",
    "_glpi_followup_attachment_document_ids",
    "_glpi_followup_record",
    "_glpi_id_reference",
    "_glpi_id_value",
    "_glpi_location_record",
    "_glpi_reference",
    "_glpi_solution_record",
    "_glpi_task_record",
    "_glpi_team_member_record",
    "_glpi_text_reference",
    "_glpi_ticket_record",
    "_glpi_ticket_user_payload",
    "_glpi_user_record",
    "_is_deleted_ticket",
    "_normalize_ticket_record",
    "_normalize_timeline_records",
    "_optional_int",
    "_optional_text",
    "_parse_glpi_datetime",
    "_resolve_glpi_member_type",
    "_strip_glpi_document_references",
    "_unwrap_timeline_item",
]
