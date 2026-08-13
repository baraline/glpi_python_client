"""RSQL filter helpers for GLPI v2 search endpoints.

The high-level client uses these helpers to build safe text-search filters
for GLPI endpoints that accept RSQL-like query expressions. All functions
return ``None`` when the supplied input is empty so callers can compose
filters without sprinkling conditional blocks at every call site.

Two properties of the v2 filter engine shape everything here, and both
fail *open*:

* **An unrecognised filter field is ignored, not rejected.** The query
  then returns the entire unfiltered table with a 200. A typo in a field
  name does not raise -- it succeeds and answers with far too many rows,
  which is why a filter that returns results is not evidence the filter
  was applied. When validating a new expression against a live instance,
  check that it returns *fewer* rows than the unfiltered baseline.
* **``;`` (AND) binds tighter than ``,`` (OR)**, so an unparenthesised
  OR group silently drops every preceding AND clause for all but its
  first alternative. See :func:`rsql_any_filter`, which exists for that
  reason and carries the measured numbers.

Nested *object* subfields can be joined (``status.id==1``,
``entity.id==3``). Nested *arrays* cannot: ``Ticket.team`` answers HTTP
500 for its contract-declared subfields and is silently ignored for every
other spelling, so actor selection has to go through the v1 search engine.
The same is expected of ``User.emails``.

Date windows live on the public surface instead, in
:mod:`glpi_python_client.rsql`, because their grammar has an end-of-day
detail that is easy to get wrong and impossible to notice.
"""

from __future__ import annotations


def rsql_contains_filter(field: str, value: str) -> str | None:
    """Build a contains-style RSQL filter for one text field.

    Blank input returns ``None`` so callers can skip adding the filter, while
    non-empty input is escaped before being wrapped in wildcard syntax.
    """

    text = value.strip()
    if not text:
        return None
    return f'{field}=like="*{escape_rsql_like_value(text)}*"'


def rsql_equals_filter(field: str, value: str | int | None) -> str | None:
    """Build an equality-style RSQL filter for one field.

    ``None`` and blank textual values return ``None`` so callers can compose
    filters without special-casing absent inputs.
    """

    if value is None:
        return None
    if isinstance(value, int):
        return f"{field}=={value}"
    text = value.strip()
    if not text:
        return None
    return f'{field}=="{escape_rsql_text_value(text)}"'


def rsql_any_filter(*filters: str | None) -> str | None:
    """Join non-empty RSQL filter fragments with OR semantics.

    Empty fragments are ignored and an all-empty input returns ``None``.

    The joined result is wrapped in parentheses whenever it contains more
    than one fragment. RSQL binds ``;`` (AND) tighter than ``,`` (OR), so
    an unparenthesised group silently loses every preceding AND clause for
    all but its first alternative: ``date;e==1,e==2`` parses as
    ``(date AND e==1) OR e==2``, which matches every ``e==2`` ticket
    regardless of the date window. Measured against a live GLPI 11
    instance, the unparenthesised form returned 16,245 tickets where the
    parenthesised form correctly returned 1,552.
    """

    parts = [fragment for fragment in filters if fragment]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return "(" + ",".join(parts) + ")"


def rsql_all_filter(*filters: str | None) -> str | None:
    """Join non-empty RSQL filter fragments with AND semantics.

    Empty fragments are ignored and an all-empty input returns ``None``.
    """

    parts = [fragment for fragment in filters if fragment]
    if not parts:
        return None
    return ";".join(parts)


def escape_rsql_like_value(value: str) -> str:
    """Escape user text embedded in a quoted RSQL ``like`` value.

    The helper protects backslashes, quotes, and wildcard characters so
    caller input is treated as text instead of modifying the filter
    expression itself.
    """

    return value.replace("\\", "\\\\").replace('"', '\\"').replace("*", "\\*")


def escape_rsql_text_value(value: str) -> str:
    """Escape user text embedded in a quoted RSQL equality value.

    The helper protects backslashes and double quotes so caller input remains
    a literal value inside the generated RSQL expression.
    """

    return value.replace("\\", "\\\\").replace('"', '\\"')


__all__ = [
    "escape_rsql_like_value",
    "escape_rsql_text_value",
    "rsql_all_filter",
    "rsql_any_filter",
    "rsql_contains_filter",
    "rsql_equals_filter",
]
