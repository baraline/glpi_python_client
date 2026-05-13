"""Scalar coercion helpers for GLPI records.

These helpers centralize the small normalization rules used repeatedly while
parsing loosely typed GLPI payload values.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _parse_glpi_datetime(value: Any) -> datetime | None:
    """Parse one GLPI datetime string.

    The helper accepts ISO-like GLPI timestamps, normalizes common timezone
    suffix variants, and returns ``None`` when parsing fails.
    """

    text = _optional_text(value)
    if text is None:
        return None
    normalized = text.replace("Z", "+00:00")
    if len(normalized) >= 5 and normalized[-5] in "+-" and normalized[-3] != ":":
        normalized = f"{normalized[:-2]}:{normalized[-2:]}"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _optional_text(value: Any) -> str | None:
    """Coerce a value to stripped text when it is meaningfully present.

    Empty strings and ``None`` normalize to ``None`` so callers can treat blank
    text fields as missing data.
    """

    text = str(value).strip() if value is not None else ""
    return text or None


def _optional_int(value: Any) -> int | None:
    """Coerce a value to ``int`` when possible.

    Invalid or missing integer-like values return ``None`` instead of raising,
    which keeps record parsing tolerant of partial payloads.
    """

    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: Any) -> bool:
    """Coerce common GLPI truthy values to ``bool``.

    The helper accepts booleans, numeric sentinels, and the most common text
    spellings emitted by GLPI payloads.
    """

    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes"}
    return False


def _first_int(*values: Any) -> int | None:
    """Return the first value that can be normalized to ``int``.

    This is useful for payloads that may expose the same identifier under more
    than one candidate key.
    """

    for value in values:
        candidate = _optional_int(value)
        if candidate is not None:
            return candidate
    return None
