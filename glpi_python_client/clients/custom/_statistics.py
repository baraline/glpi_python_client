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
from typing import TypedDict

from glpi_python_client.clients.commons._filters import (
    rsql_all_filter,
    rsql_any_filter,
    rsql_contains_filter,
)
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


class TaskStatisticsResult(TypedDict):
    """Typed shape returned by :meth:`StatisticsMixin.get_task_statistics`."""

    ticket_count: int
    task_count: int
    total_duration: int
    duration_by_user: dict[str, int]
    duration_by_ticket: dict[int, int]


class TaskDurationsResult(TypedDict):
    """Typed shape returned by :meth:`StatisticsMixin.get_task_durations`."""

    start_date: str
    end_date: str
    total_duration: int
    task_count: int
    duration_by_user: dict[str, int]
    duration_by_entity: dict[str, int]
    tasks: list[dict[str, object]] | None


class UserActivityEntry(TypedDict):
    """One per-user activity bucket inside :class:`UserActivityResult`."""

    user_ids: list[int]
    tickets_as_technician: int
    tickets_as_recipient: int
    task_durations: TaskDurationsResult


class UserActivityResult(TypedDict):
    """Typed shape returned by :meth:`StatisticsMixin.get_user_activity`."""

    users: dict[str, UserActivityEntry]


class StatisticsMixin(TransportMixin):
    """Synchronous custom statistics built on the contract API mixins."""

    def get_ticket_statistics(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        default_days: int = 30,
        entity_id: int | None = None,
        entity_name: str | None = None,
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
            ISO ``YYYY-MM-DD`` start of the window (inclusive from
            00:00:00). Defaults to ``end_date - default_days + 1``
            when omitted.
        end_date : str | None, optional
            ISO ``YYYY-MM-DD`` end of the window (inclusive through
            23:59:59). Defaults to today.
        default_days : int, optional
            Span in days used when ``start_date`` is omitted (defaults
            to 30 and must be a positive integer).
        entity_id : int | None, optional
            When provided, restricts results to tickets belonging to the
            entity with this GLPI identifier.
        entity_name : str | None, optional
            When provided (and ``entity_id`` is ``None``), the name is
            resolved via ``search_entities`` and the matched entity IDs
            are used to filter tickets. If no entity matches,
            ``{"entities": {}}`` is returned immediately.
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

        entity_filter: str | None = None
        if entity_id is not None:
            entity_filter = f"entities_id=={entity_id}"
        elif entity_name is not None:
            name_filter = rsql_contains_filter("name", entity_name) or ""
            entities = self.search_entities(  # type: ignore[attr-defined]
                rsql_filter=name_filter,
                limit=200,
            )
            if not entities:
                return {"entities": {}}
            entity_filter = rsql_any_filter(
                *(f"entities_id=={e.id}" for e in entities if e.id is not None)
            )
        date_filter = f"date_creation=ge={start.isoformat()};"
        date_filter += f"date_creation=le={end.isoformat()} 23:59:59"
        query = rsql_all_filter(
            date_filter,
            entity_filter,
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
    ) -> TaskStatisticsResult:
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
        TaskStatisticsResult
            Mapping with ``ticket_count``, ``task_count``,
            ``total_duration``, ``duration_by_user``, and
            ``duration_by_ticket`` entries (durations are integer
            seconds, matching the GLPI ``duration`` field).
        """

        if not ticket_ids:
            return TaskStatisticsResult(
                ticket_count=0,
                task_count=0,
                total_duration=0,
                duration_by_user={},
                duration_by_ticket={},
            )

        results: list[list[GetTicketTask]] = [
            self.list_ticket_tasks(ticket_id)  # type: ignore[attr-defined]
            for ticket_id in ticket_ids
        ]
        flattened: list[GetTicketTask] = [task for batch in results for task in batch]
        return _summarize_tasks(ticket_ids, flattened)

    def get_task_durations(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        default_days: int = 30,
        entity_id: int | None = None,
        entity_name: str | None = None,
        user_id: int | None = None,
        user_editor_id: int | None = None,
        user_recipient_id: int | None = None,
        extra_filter: str | None = None,
        return_task_details: bool = False,
    ) -> TaskDurationsResult:
        """Return task duration totals with optional per-task detail.

        Builds an RSQL filter from the supplied parameters, collects all
        matching tickets by iterating :meth:`iter_search_tickets`, computes
        ``duration_by_entity`` by grouping :meth:`get_task_statistics`
        results against the per-ticket entity map, and optionally returns a
        flat list of individual task records.

        Parameters
        ----------
        start_date : str | None, optional
            ISO ``YYYY-MM-DD`` start of the window (inclusive from
            00:00:00). Defaults to ``end_date - default_days + 1``
            when omitted.
        end_date : str | None, optional
            ISO ``YYYY-MM-DD`` end of the window (inclusive through
            23:59:59). Defaults to today.
        default_days : int, optional
            Span in days used when ``start_date`` is omitted (defaults
            to 30 and must be a positive integer).
        entity_id : int | None, optional
            Restrict to tickets in this entity.
        entity_name : str | None, optional
            Resolve entity by name and restrict to matched entities
            (ignored when ``entity_id`` is given).
        user_id : int | None, optional
            Restrict to tickets where the user is an assignee or
            requester (OR semantics across both roles).
        user_editor_id : int | None, optional
            Restrict to tickets last updated by this user.
        user_recipient_id : int | None, optional
            Restrict to tickets where this user is the requester.
        extra_filter : str | None, optional
            Optional raw RSQL fragment appended as an AND clause.
        return_task_details : bool, optional
            When ``True``, include a ``tasks`` list of individual task
            records in the returned mapping (default ``False``).

        Returns
        -------
        TaskDurationsResult
            Mapping with ``start_date``, ``end_date``, ``total_duration``,
            ``task_count``, ``duration_by_user``, ``duration_by_entity``,
            and ``tasks`` (``None`` when ``return_task_details=False``).

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
        date_filter = f"date_creation=ge={start.isoformat()};"
        date_filter += f"date_creation=le={end.isoformat()} 23:59:59"

        entity_filter: str | None = None
        if entity_id is not None:
            entity_filter = f"entities_id=={entity_id}"
        elif entity_name is not None:
            name_filter = rsql_contains_filter("name", entity_name) or ""
            entities = self.search_entities(  # type: ignore[attr-defined]
                rsql_filter=name_filter,
                limit=200,
            )
            if not entities:
                return TaskDurationsResult(
                    start_date=start.isoformat(),
                    end_date=end.isoformat(),
                    total_duration=0,
                    task_count=0,
                    duration_by_user={},
                    duration_by_entity={},
                    tasks=None,
                )
            entity_filter = rsql_any_filter(
                *(f"entities_id=={e.id}" for e in entities if e.id is not None)
            )

        user_filter: str | None = None
        if user_id is not None:
            user_filter = rsql_any_filter(
                f"users_id_assign=={user_id}",
                f"users_id_requester=={user_id}",
            )

        editor_filter: str | None = None
        if user_editor_id is not None:
            editor_filter = f"users_id_lastupdater=={user_editor_id}"

        recipient_filter: str | None = None
        if user_recipient_id is not None:
            recipient_filter = f"users_id_requester=={user_recipient_id}"

        rsql_filter = (
            rsql_all_filter(
                date_filter,
                entity_filter,
                user_filter,
                editor_filter,
                recipient_filter,
                extra_filter,
            )
            or ""
        )

        ticket_ids: list[int] = []
        ticket_entity_map: dict[int, str] = {}
        for batch in self.iter_search_tickets(  # type: ignore[attr-defined]
            rsql_filter,
            batch_size=200,
        ):
            for ticket in batch:
                if ticket.id is not None:
                    ticket_ids.append(ticket.id)
                    ticket_entity_map[ticket.id] = _entity_key(ticket.entity)

        result = self.get_task_statistics(ticket_ids)
        duration_by_ticket = result["duration_by_ticket"]

        duration_by_entity: defaultdict[str, int] = defaultdict(int)
        for tid, dur in duration_by_ticket.items():
            entity_key = ticket_entity_map.get(int(tid), "unknown")
            duration_by_entity[entity_key] += int(dur)

        task_details: list[dict[str, object]] | None = None
        if return_task_details:
            task_details = []
            for tid, dur in duration_by_ticket.items():
                if int(dur) == 0:
                    continue
                for task in self.list_ticket_tasks(int(tid)):  # type: ignore[attr-defined]
                    task_details.append(
                        {
                            "task_id": task.id,
                            "ticket_id": int(tid),
                            "duration": int(task.duration or 0),
                            "user_id": task.user.id if task.user else None,
                            "user_name": task.user.name if task.user else None,
                            "date": str(task.date_creation or ""),
                        }
                    )

        return TaskDurationsResult(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            total_duration=int(result["total_duration"]),
            task_count=int(result["task_count"]),
            duration_by_user=result["duration_by_user"],
            duration_by_entity=dict(duration_by_entity),
            tasks=task_details,
        )

    def get_user_activity(
        self,
        *,
        user_id: int | None = None,
        username: str | None = None,
        realname: str | None = None,
        firstname: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        default_days: int = 30,
    ) -> UserActivityResult:
        """Return per-user GLPI activity aggregated across tickets and tasks.

        Aggregates tickets where each matched user is an assignee, tickets
        where the user is a requester, and task durations over the requested
        date window. When multiple users resolve to the same display key
        their results are merged.

        Parameters
        ----------
        user_id : int | None, optional
            Identify the user by GLPI numeric identifier.
        username : str | None, optional
            Filter by username (substring match).
        realname : str | None, optional
            Filter by family name (substring match).
        firstname : str | None, optional
            Filter by given name (substring match).
        start_date : str | None, optional
            ISO ``YYYY-MM-DD`` start of the activity window (inclusive
            from 00:00:00).
        end_date : str | None, optional
            ISO ``YYYY-MM-DD`` end of the activity window (inclusive
            through 23:59:59). Defaults to today.
        default_days : int, optional
            Span in days used when ``start_date`` is omitted (default 30).

        Returns
        -------
        UserActivityResult
            Mapping with one ``users`` key. Each user key maps to a
            :class:`UserActivityEntry` with ``user_ids``,
            ``tickets_as_technician``, ``tickets_as_recipient``, and
            ``task_durations``.

        Raises
        ------
        ValueError
            If none of ``user_id``, ``username``, ``realname``, or
            ``firstname`` are supplied, or if the supplied criteria match
            no GLPI users.
        """

        if all(v is None for v in (user_id, username, realname, firstname)):
            raise ValueError(
                "At least one of user_id, username, realname, or "
                "firstname must be supplied"
            )

        start, end = _resolve_window(
            start_date=start_date,
            end_date=end_date,
            default_days=default_days,
        )

        if user_id is not None:
            resolved_user_ids: list[int] = [user_id]
            user_display_map: dict[int, str] = {user_id: str(user_id)}
        else:
            name_parts = [
                rsql_contains_filter("username", username) if username else None,
                rsql_contains_filter("realname", realname) if realname else None,
                rsql_contains_filter("firstname", firstname) if firstname else None,
            ]
            user_rsql = rsql_all_filter(*name_parts) or ""
            matched_users = self.search_users(  # type: ignore[attr-defined]
                rsql_filter=user_rsql,
                limit=200,
            )
            if not matched_users:
                raise ValueError("No users matched the supplied criteria")
            resolved_user_ids = [u.id for u in matched_users if u.id is not None]
            user_display_map = {
                u.id: (
                    f"{u.firstname or ''} {u.realname or ''}".strip()
                    or u.username
                    or str(u.id)
                )
                for u in matched_users
                if u.id is not None
            }

        date_range = f"date_creation=ge={start.isoformat()};"
        date_range += f"date_creation=le={end.isoformat()} 23:59:59"

        users_output: dict[str, UserActivityEntry] = {}
        for uid in resolved_user_ids:
            display_key = user_display_map.get(uid, str(uid))
            tech_count = 0
            for batch in self.iter_search_tickets(  # type: ignore[attr-defined]
                f"users_id_assign=={uid};{date_range}",
                batch_size=200,
            ):
                tech_count += len(batch)
            recipient_count = 0
            for batch in self.iter_search_tickets(  # type: ignore[attr-defined]
                f"users_id_requester=={uid};{date_range}",
                batch_size=200,
            ):
                recipient_count += len(batch)
            task_dur = self.get_task_durations(
                start_date=start_date,
                end_date=end_date,
                default_days=default_days,
                user_id=uid,
            )
            # Drop the optional ``tasks`` payload before storing on the
            # per-user entry; the activity summary keeps only aggregated
            # counters per user.
            task_dur_clean: TaskDurationsResult = TaskDurationsResult(
                start_date=task_dur["start_date"],
                end_date=task_dur["end_date"],
                total_duration=task_dur["total_duration"],
                task_count=task_dur["task_count"],
                duration_by_user=dict(task_dur["duration_by_user"]),
                duration_by_entity=dict(task_dur["duration_by_entity"]),
                tasks=None,
            )

            if display_key in users_output:
                existing = users_output[display_key]
                existing["user_ids"] = [*existing["user_ids"], uid]
                existing["tickets_as_technician"] += tech_count
                existing["tickets_as_recipient"] += recipient_count
                existing["task_durations"] = _merge_task_durations(
                    existing["task_durations"], task_dur_clean
                )
            else:
                users_output[display_key] = UserActivityEntry(
                    user_ids=[uid],
                    tickets_as_technician=tech_count,
                    tickets_as_recipient=recipient_count,
                    task_durations=task_dur_clean,
                )

        return UserActivityResult(users=users_output)


def _merge_task_durations(
    prev: TaskDurationsResult, new: TaskDurationsResult
) -> TaskDurationsResult:
    """Merge two task-duration aggregates summing every counter.

    The returned ``start_date`` / ``end_date`` are inherited from
    ``prev`` since the helper is only used to fold per-user results that
    were computed over the same window. The ``tasks`` payload is dropped
    because the merged aggregate is part of a user activity report and
    not a detail listing.
    """

    merged_by_user: dict[str, int] = dict(prev["duration_by_user"])
    for k, v in new["duration_by_user"].items():
        merged_by_user[k] = merged_by_user.get(k, 0) + int(v)
    merged_by_entity: dict[str, int] = dict(prev["duration_by_entity"])
    for k, v in new["duration_by_entity"].items():
        merged_by_entity[k] = merged_by_entity.get(k, 0) + int(v)
    return TaskDurationsResult(
        start_date=prev["start_date"],
        end_date=prev["end_date"],
        total_duration=prev["total_duration"] + new["total_duration"],
        task_count=prev["task_count"] + new["task_count"],
        duration_by_user=merged_by_user,
        duration_by_entity=merged_by_entity,
        tasks=None,
    )


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
) -> TaskStatisticsResult:
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
    return TaskStatisticsResult(
        ticket_count=len(ticket_ids),
        task_count=len(tasks),
        total_duration=total_duration,
        duration_by_user=dict(duration_by_user),
        duration_by_ticket=dict(duration_by_ticket),
    )


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
