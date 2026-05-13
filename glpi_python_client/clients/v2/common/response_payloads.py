"""Response payload extraction helpers for GLPI v2 clients.

These functions turn raw JSON and timeline payloads into predictable lists of
mapping items before higher-level parsers convert them into typed models.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

import requests

from glpi_python_client.content.records.core.normalization import (
    _normalize_timeline_records,
)

RecordT = TypeVar("RecordT")


def list_payload_items(payload: object) -> list[dict[str, Any]]:
    """Return dictionary items from one plain JSON list payload.

    Non-list payloads are treated as empty so callers can safely use this on
    API responses that may vary or fail validation upstream.
    """

    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def timeline_payload_items(payload: object) -> list[dict[str, Any]]:
    """Return dictionary items from one GLPI timeline payload.

    Timeline payloads go through the shared normalization step first because
    GLPI can nest timeline items in multiple container shapes.
    """

    return [
        item for item in _normalize_timeline_records(payload) if isinstance(item, dict)
    ]


def list_payload_records(
    payload: object,
    *,
    record_factory: Callable[[dict[str, Any]], RecordT | None],
) -> list[RecordT]:
    """Build typed records from one plain JSON list payload.

    The provided factory may return ``None`` to skip individual raw items while
    preserving the rest of the batch.
    """

    records: list[RecordT] = []
    for item in list_payload_items(payload):
        record = record_factory(item)
        if record is not None:
            records.append(record)
    return records


def timeline_records_from_response(
    response: requests.Response,
    *,
    record_factory: Callable[[dict[str, Any]], RecordT],
) -> list[RecordT]:
    """Build typed records from one successful GLPI timeline response.

    Unlike plain list payload handling, timeline parsing assumes each normalized
    item should produce a record and lets the record factory raise on invalid
    data.
    """

    return [record_factory(item) for item in timeline_payload_items(response.json())]
