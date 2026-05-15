"""Shared analytics helpers for GLPI v2 clients.

These helpers keep date-window parsing, label normalization, and aggregation
logic reusable across the sync and async high-level analytics mixins.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from enum import IntEnum

from glpi_python_client.clients.v2.common.filters import (
    rsql_all_filter,
    rsql_any_filter,
    rsql_contains_filter,
    rsql_equals_filter,
)
from glpi_python_client.models import (
    GlpiTask,
    GlpiTicket,
    GlpiUser,
)


def resolve_date_window(
    *,
    start_date: str | None,
    end_date: str | None,
    default_days: int,
) -> tuple[date, date]:
    """Return the validated inclusive date window used by analytics helpers.

    ``default_days`` is used only when ``start_date`` is omitted. The computed
    window is inclusive at both ends so a ``default_days`` value of ``30``
    produces a 30-day range including the end date.
    """

    if default_days < 1:
        raise ValueError("default_days must be a positive integer")

    parsed_end = _parse_date_text(end_date) if end_date is not None else date.today()
    if start_date is None:
        parsed_start = parsed_end - timedelta(days=default_days - 1)
    else:
        parsed_start = _parse_date_text(start_date)

    if parsed_start > parsed_end:
        raise ValueError("start_date must be less than or equal to end_date")
    return parsed_start, parsed_end


def build_entity_search_filter(entity_name: str | None) -> str | None:
    """Return the composed RSQL filter used to search entities by name.

    Both the short entity name and the GLPI complete-name field are considered
    when available.
    """

    if entity_name is None:
        return None
    return rsql_any_filter(
        rsql_contains_filter("name", entity_name),
        rsql_contains_filter("completename", entity_name),
        rsql_contains_filter("complete_name", entity_name),
    )


def build_user_search_filter(
    *,
    user_id: int | str | None,
    email: str | None,
    name: str | None,
    firstname: str | None,
) -> str | None:
    """Return the composed RSQL filter used to resolve GLPI users.

    The helper joins all supplied identifiers with AND semantics while allowing
    a broader OR match across the common name-like user fields.
    """

    name_filter = None
    if name is not None:
        name_filter = rsql_any_filter(
            rsql_contains_filter("name", name),
            rsql_contains_filter("realname", name),
            rsql_contains_filter("username", name),
        )
    return rsql_all_filter(
        rsql_equals_filter("id", int(user_id))
        if isinstance(user_id, str) and user_id.isdigit()
        else rsql_equals_filter("id", user_id if isinstance(user_id, int) else None),
        rsql_equals_filter("email", email),
        name_filter,
        rsql_contains_filter("firstname", firstname) if firstname is not None else None,
    )


def build_date_range_filter(field: str, *, start: date, end: date) -> str:
    """Return one inclusive GLPI date-range filter string.

    The returned fragment can be combined with other filters using
    ``combine_rsql_filters``.
    """

    return f"{field}=ge={start.isoformat()};{field}=le={end.isoformat()}"


def combine_rsql_filters(*filters: str | None) -> str | None:
    """Join non-empty RSQL fragments with AND semantics.

    Empty fragments are ignored and an all-empty input returns ``None``.
    """

    parts = [fragment for fragment in filters if fragment]
    if not parts:
        return None
    return ";".join(parts)


def glpi_reference_id(value: object) -> int | None:
    """Return the integer identifier carried by one GLPI reference value.

    Mappings, integers, and integer-like strings are accepted. Any other value
    returns ``None``.
    """

    if isinstance(value, Mapping):
        return glpi_reference_id(value.get("id"))
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def glpi_reference_name(value: object) -> str | None:
    """Return the most descriptive name carried by one GLPI reference value.

    ``complete_name`` and ``completename`` take precedence over the shorter
    ``name`` field when they are available.
    """

    if not isinstance(value, Mapping):
        return None
    for key in ("complete_name", "completename", "name"):
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def glpi_user_id(user: GlpiUser | None) -> str | None:
    """Return the normalized GLPI user identifier from one user object.

    Missing users or blank identifiers return ``None``.
    """

    if user is None:
        return None
    if user.user_id is None:
        return None
    return str(user.user_id)


def glpi_user_label(user: GlpiUser | None, *, fallback: str | None = None) -> str:
    """Return the best available public label for one GLPI user.

    The label prefers explicit names, then email, then the user identifier.
    """

    for candidate in (
        user.name if user is not None else None,
        user.email if user is not None else None,
        glpi_user_id(user),
        fallback,
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return "unknown"


def glpi_entity_label(
    entity: object,
    *,
    entity_labels: Mapping[int, str] | None = None,
) -> str:
    """Return the best available public label for one GLPI entity reference.

    Explicit resolved labels take precedence over names embedded directly in the
    task or ticket payload.
    """

    entity_id = glpi_reference_id(entity)
    if entity_id is not None and entity_labels is not None:
        label = entity_labels.get(entity_id)
        if label:
            return label
    name = glpi_reference_name(entity)
    if name is not None:
        return name
    if entity_id is not None:
        return str(entity_id)
    return "unknown"


def enum_label(enum_type: type[IntEnum], value: int | None) -> str:
    """Return the enum member name for one numeric GLPI value.

    Unknown numeric values fall back to their string form instead of raising.
    """

    if value is None:
        return "UNKNOWN"
    try:
        return enum_type(value).name
    except ValueError:
        return str(value)


def summarize_task_durations(
    tasks: list[GlpiTask],
    *,
    start: date,
    end: date,
    ticket_cache: Mapping[str, GlpiTicket],
    user_labels: Mapping[str, str] | None = None,
    entity_labels: Mapping[int, str] | None = None,
    include_tasks: bool = False,
) -> dict[str, object]:
    """Return one public task-duration summary for the provided task list.

    The helper keeps the public output shape consistent across the sync and
    async analytics methods.
    """

    duration_by_user: dict[str, int] = {}
    duration_by_entity: dict[str, int] = {}
    total_duration = 0

    for task in tasks:
        duration = task.duration or 0
        total_duration += duration

        user_id = task.user_id or glpi_user_id(task.user)
        user_label = None
        if user_id is not None and user_labels is not None:
            user_label = user_labels.get(user_id)
        _increment_counter(
            duration_by_user,
            glpi_user_label(task.user, fallback=user_label or user_id),
            duration,
        )

        ticket = ticket_cache.get(task.ticket_id or "")
        entity_reference = (
            task.entity
            if task.entity is not None
            else ticket.entity
            if ticket
            else None
        )
        _increment_counter(
            duration_by_entity,
            glpi_entity_label(entity_reference, entity_labels=entity_labels),
            duration,
        )

    result: dict[str, object] = {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_duration": total_duration,
        "task_count": len(tasks),
        "duration_by_user": duration_by_user,
        "duration_by_entity": duration_by_entity,
    }
    if include_tasks:
        result["tasks"] = list(tasks)
    return result


def summarize_ticket_statistics(
    tickets: list[GlpiTicket],
    *,
    entity_labels: Mapping[int, str] | None = None,
    status_enum: type[IntEnum],
    priority_enum: type[IntEnum],
    type_enum: type[IntEnum],
) -> dict[str, object]:
    """Return one public ticket-statistics summary for the provided tickets.

    Counts are grouped by entity and then broken down by status, priority, and
    type labels.
    """

    entities: dict[str, dict[str, object]] = {}
    for ticket in tickets:
        entity_key = glpi_entity_label(ticket.entity, entity_labels=entity_labels)
        bucket = entities.setdefault(
            entity_key,
            {
                "total": 0,
                "by_status": {},
                "by_priority": {},
                "by_type": {},
            },
        )
        bucket["total"] = int(bucket["total"]) + 1
        by_status = bucket["by_status"]
        by_priority = bucket["by_priority"]
        by_type = bucket["by_type"]
        if isinstance(by_status, dict):
            _increment_counter(
                by_status,
                enum_label(status_enum, glpi_reference_id(ticket.status)),
            )
        if isinstance(by_priority, dict):
            _increment_counter(by_priority, enum_label(priority_enum, ticket.priority))
        if isinstance(by_type, dict):
            _increment_counter(by_type, enum_label(type_enum, ticket.type))
    return {"entities": entities}


def normalized_user_id_list(*user_ids: str | None) -> list[int | str]:
    """Return one normalized list of user IDs for public report output.

    Integer-like user IDs are returned as ``int`` objects and the original
    order is preserved while duplicates are removed.
    """

    normalized: list[int | str] = []
    seen: set[int | str] = set()
    for user_id in user_ids:
        if user_id is None:
            continue
        candidate: int | str = int(user_id) if user_id.isdigit() else user_id
        if candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


def unique_user_key(
    existing: Mapping[str, object], label: str, user_id: str | None
) -> str:
    """Return one stable key for a user entry inside an activity report.

    Duplicate labels are disambiguated with the user identifier when available.
    """

    if label not in existing:
        return label
    if user_id:
        disambiguated = f"{label} ({user_id})"
        if disambiguated not in existing:
            return disambiguated
    suffix = 2
    while f"{label} #{suffix}" in existing:
        suffix += 1
    return f"{label} #{suffix}"


def _parse_date_text(value: str) -> date:
    """Parse one ISO ``YYYY-MM-DD`` date string.

    Invalid values raise ``ValueError`` with a user-facing message that is
    reused by the public analytics helpers.
    """

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid date {value!r}; expected YYYY-MM-DD") from exc


def _increment_counter(counter: dict[str, int], key: str, amount: int = 1) -> None:
    """Increment one string-keyed integer counter mapping.

    The helper creates missing keys automatically and keeps aggregation code
    small and uniform.
    """

    counter[key] = counter.get(key, 0) + amount
