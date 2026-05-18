"""Lightweight statistics helpers built from the API mixins.

The mixin exposes simple aggregations over ticket and ticket-task results
returned by the contract-aligned helpers in
:mod:`glpi_python_client.clients.api`. These operations are intentionally
kept small and do not perform name resolution or rich label formatting; the
caller can correlate the returned numeric identifiers with the dedicated
``search_*`` helpers when required.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from glpi_python_client.clients.commons._filters import rsql_all_filter
from glpi_python_client.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema._common import (
    IdNameCompletenameRef,
    IdNameRef,
)
from glpi_python_client.models.api_schema.assistance._ticket import GetTicket
from glpi_python_client.models.api_schema.assistance.timeline._task import (
    GetTicketTask,
)
from glpi_python_client.models.api_schema.enums import (
    GlpiPriority,
    GlpiTicketType,
)


class StatisticsMixin(TransportMixin):
    """Synchronous custom statistics built on the contract API mixins."""

    def get_ticket_statistics(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        default_days: int = 30,
        extra_filter: str | None = None,
    ) -> dict[str, object]:
        """Return ticket counts grouped by entity, status, priority, and type.

        The date window is applied to the GLPI ``date_creation`` field
        and results are aggregated locally in Python. Returned
        identifiers are the raw GLPI numeric values that callers can
        resolve with the dedicated ``search_*`` helpers when human
        labels are needed.

        Parameters
        ----------
        start_date : str | None, optional
            ISO ``YYYY-MM-DD`` start of the window. Defaults to
            ``end_date - default_days + 1`` when omitted.
        end_date : str | None, optional
            ISO ``YYYY-MM-DD`` end of the window. Defaults to today.
        default_days : int, optional
            Span in days used when ``start_date`` is omitted (defaults
            to 30 and must be a positive integer).
        extra_filter : str | None, optional
            Optional raw RSQL fragment to ``AND`` with the date window
            on the server side.

        Returns
        -------
        dict[str, object]
            Mapping with one ``entities`` key listing per-entity
            aggregates. Each entity bucket exposes ``total``,
            ``by_status``, ``by_priority``, and ``by_type`` counters.

        Raises
        ------
        ValueError
            If ``default_days < 1`` or ``start_date > end_date``.
        """

        start, end = _resolve_window(
            start_date=start_date,
            end_date=end_date,
            default_days=default_days,
        )
        query = rsql_all_filter(
            f"date_creation=ge={start.isoformat()};date_creation=le={end.isoformat()}",
            extra_filter,
        )
        tickets: list[GetTicket] = self.search_tickets(  # type: ignore[attr-defined]
            rsql_filter=query or "",
            limit=200,
        )
        return _summarize_tickets(tickets)

    def get_task_statistics(
        self,
        ticket_ids: list[int],
    ) -> dict[str, object]:
        """Return task duration totals grouped by user and ticket.

        The helper expects a list of ticket identifiers because GLPI
        does not publish a global task collection endpoint. Callers
        typically gather the relevant ticket identifiers through
        ``search_tickets`` first.

        Parameters
        ----------
        ticket_ids : list[int]
            Identifiers of the tickets whose tasks should be aggregated.
            An empty list returns zeroed totals without any HTTP call.

        Returns
        -------
        dict[str, object]
            Mapping with ``ticket_count``, ``task_count``,
            ``total_duration``, ``duration_by_user``, and
            ``duration_by_ticket`` entries (durations are integer
            seconds, matching the GLPI ``duration`` field).
        """

        if not ticket_ids:
            return {
                "ticket_count": 0,
                "task_count": 0,
                "total_duration": 0,
                "duration_by_user": {},
                "duration_by_ticket": {},
            }

        results: list[list[GetTicketTask]] = [
            self.list_ticket_tasks(ticket_id)  # type: ignore[attr-defined]
            for ticket_id in ticket_ids
        ]
        flattened: list[GetTicketTask] = [task for batch in results for task in batch]
        return _summarize_tasks(ticket_ids, flattened)


def _resolve_window(
    *,
    start_date: str | None,
    end_date: str | None,
    default_days: int,
) -> tuple[date, date]:
    """Resolve a date window from optional ISO inputs and a default span.

    Validation matches the legacy analytics helper: positive default span,
    parsed ISO dates, and ``start <= end``.
    """

    if default_days < 1:
        raise ValueError("default_days must be a positive integer")
    parsed_end = date.fromisoformat(end_date) if end_date else date.today()
    parsed_start = (
        date.fromisoformat(start_date)
        if start_date
        else parsed_end - timedelta(days=default_days - 1)
    )
    if parsed_start > parsed_end:
        raise ValueError("start_date must be less than or equal to end_date")
    return parsed_start, parsed_end


def _summarize_tickets(tickets: list[GetTicket]) -> dict[str, object]:
    """Group tickets by entity and break each entity down by attribute."""

    entities: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "total": 0,
            "by_status": defaultdict(int),
            "by_priority": defaultdict(int),
            "by_type": defaultdict(int),
        }
    )
    for ticket in tickets:
        entity_key = _entity_key(ticket.entity)
        bucket = entities[entity_key]
        bucket["total"] = int(bucket["total"]) + 1  # type: ignore[call-overload]
        _count_status(bucket["by_status"], ticket.status)  # type: ignore[arg-type]
        _count_enum(bucket["by_priority"], ticket.priority, GlpiPriority)  # type: ignore[arg-type]
        _count_enum(bucket["by_type"], ticket.type, GlpiTicketType)  # type: ignore[arg-type]
    return {"entities": {key: _freeze_bucket(value) for key, value in entities.items()}}


def _summarize_tasks(
    ticket_ids: list[int], tasks: list[GetTicketTask]
) -> dict[str, object]:
    """Aggregate one task list by user and parent ticket identifier."""

    duration_by_user: defaultdict[str, int] = defaultdict(int)
    duration_by_ticket: defaultdict[int, int] = defaultdict(int)
    total_duration = 0
    for task in tasks:
        duration = int(task.duration or 0)
        total_duration += duration
        duration_by_user[_user_key(task.user)] += duration
        if task.tickets_id is not None:
            duration_by_ticket[task.tickets_id] += duration
    return {
        "ticket_count": len(ticket_ids),
        "task_count": len(tasks),
        "total_duration": total_duration,
        "duration_by_user": dict(duration_by_user),
        "duration_by_ticket": dict(duration_by_ticket),
    }


def _entity_key(entity: IdNameCompletenameRef | None) -> str:
    """Return one stable identifier string for the provided entity reference.

    Numeric entity identifiers are preferred so the output stays stable when
    the entity name changes between runs.
    """

    if entity is None:
        return "unknown"
    if entity.id is not None:
        return str(entity.id)
    return entity.name or "unknown"


def _user_key(user: IdNameRef | None) -> str:
    """Return one stable identifier string for the provided user reference."""

    if user is None:
        return "unknown"
    if user.id is not None:
        return str(user.id)
    return user.name or "unknown"


def _count_status(counter: defaultdict[str, int], status: IdNameRef | None) -> None:
    """Increment one status counter using the GLPI numeric identifier."""

    if status is None:
        counter["UNKNOWN"] += 1
        return
    counter[str(status.id) if status.id is not None else status.name or "UNKNOWN"] += 1


def _count_enum(counter: defaultdict[str, int], value: object, enum_type: type) -> None:
    """Increment one counter using the IntEnum member name when possible."""

    if value is None:
        counter["UNKNOWN"] += 1
        return
    try:
        counter[enum_type(value).name] += 1
    except ValueError:
        counter[str(value)] += 1


def _freeze_bucket(bucket: dict[str, object]) -> dict[str, object]:
    """Convert defaultdict counters into plain dicts for the public output."""

    return {
        "total": bucket["total"],
        "by_status": dict(bucket["by_status"]),  # type: ignore[call-overload]
        "by_priority": dict(bucket["by_priority"]),  # type: ignore[call-overload]
        "by_type": dict(bucket["by_type"]),  # type: ignore[call-overload]
    }


__all__ = ["StatisticsMixin"]
