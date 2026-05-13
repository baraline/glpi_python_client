"""RSQL filter helpers for GLPI v2 search endpoints.

The high-level client uses these helpers to build safe text-search filters for
GLPI endpoints that accept RSQL-like query expressions.
"""

from __future__ import annotations


def rsql_contains_filter(field: str, value: str) -> str | None:
    """Build a contains-style RSQL filter for one text field.

    Blank search input returns ``None`` so callers can skip adding the filter,
    while non-empty input is escaped before being wrapped in wildcard syntax.
    """

    text = value.strip()
    if not text:
        return None
    return f'{field}=like="*{escape_rsql_like_value(text)}*"'


def escape_rsql_like_value(value: str) -> str:
    """Escape user text embedded in a quoted RSQL ``like`` value.

    The helper protects backslashes, quotes, and wildcard characters so caller
    input is treated as text instead of modifying the filter expression.
    """

    return value.replace("\\", "\\\\").replace('"', '\\"').replace("*", "\\*")
