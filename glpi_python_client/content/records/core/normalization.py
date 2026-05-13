"""Raw GLPI payload normalization helpers.

These helpers smooth over the small shape differences between GLPI ticket and
timeline payloads before the model-specific parsers consume them.
"""

from __future__ import annotations

from typing import Any


def _normalize_ticket_record(data: object) -> dict[str, Any] | object:
    """Return a shallow mapping copy for one raw GLPI ticket payload.

    Ticket payloads are usually already flat mappings, so normalization here is
    limited to copying dictionaries before downstream mutation.
    """

    if not isinstance(data, dict):
        return data
    return dict(data)


def _normalize_timeline_records(data: object) -> list[dict[str, Any]]:
    """Normalize one GLPI timeline payload to a list of item mappings.

    GLPI timeline responses may contain wrapper objects around the actual item
    payload. This helper unwraps those entries and keeps only mapping items.
    """

    if not isinstance(data, list):
        return []

    records: list[dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        item = _unwrap_timeline_item(entry)
        if isinstance(item, dict):
            records.append(dict(item))
    return records


def _unwrap_timeline_item(entry: dict[str, Any]) -> dict[str, Any]:
    """Return the nested timeline item mapping when GLPI wraps it in ``item``.

    Some timeline endpoints return an outer record with the real payload stored
    under the ``item`` key; others already return the payload directly.
    """

    if "item" in entry and isinstance(entry["item"], dict):
        return entry["item"]
    return entry
