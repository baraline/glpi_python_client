"""Lightweight statistics helpers built from the API mixins.

The mixin exposes simple aggregations over ticket and ticket-task results
returned by the contract-aligned helpers in
:mod:`glpi_python_client._async.clients.api`. These operations are intentionally
kept small and do not perform name resolution or rich label formatting; the
caller can correlate the returned numeric identifiers with the dedicated
``search_*`` helpers when required.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import TypedDict

from glpi_python_client._async.clients.commons._filters import (
    rsql_all_filter,
    rsql_any_filter,
    rsql_contains_filter,
)
from glpi_python_client._async.clients.commons._transport import TransportMixin
from glpi_python_client._errors import GlpiValidationError
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

#: The GLPI v2 ticket search includes soft-deleted ("trashed") tickets by
#: default, while the v1 search excludes them. Every aggregation here is
#: about live work, so the v2 queries pin the flag explicitly. Measured on
#: a live GLPI 11 instance: 59,690 live + 258 trashed = 59,948 unfiltered,
#: and for some users the trashed rows were the large majority of matches.
_LIVE_TICKETS = "is_deleted==false"

#: v1 ``search/Ticket`` searchOption ids. The v2 API exposes no filterable
#: assignee at all -- its ``team`` array cannot be joined by the RSQL engine
#: (the contract-declared subfields answer HTTP 500 and every other spelling
#: is silently ignored) -- so actor-based selection has to go through v1.
_V1_SO_TICKET_ID = 2
_V1_SO_REQUESTER = 4  # "Demandeur" -- glpi_tickets_users.users_id, type=1
_V1_SO_ASSIGNEE = 5  # "Technicien" -- glpi_tickets_users.users_id, type=2

#: v1 rejects a ``range`` that starts past the end of the result set with
#: HTTP 400, so paging is bounded by ``totalcount`` rather than by probing.
_V1_SEARCH_PAGE_SIZE = 1000

#: Rows fetched per page from the v1 ``TicketTask`` collection.
_V1_TASK_PAGE_SIZE = 1000

#: Above this many tickets, one bulk v1 task sweep beats a per-ticket v2
#: request each. The sweep costs one page per 1000 tasks created since the
#: window opened -- typically one or two -- while the per-ticket path costs
#: exactly ``len(ticket_ids)`` requests. Below the threshold the per-ticket
#: path is cheaper and needs no v1 session, so it stays the default.
_V1_TASK_BULK_THRESHOLD = 25


def _validate_actor_id(value: int, parameter: str) -> int:
    """Return ``value`` when it is usable as a GLPI user identifier.

    The v1 search engine fails *open* on a malformed actor value instead of
    rejecting it, so a bad id yields a plausible-looking but meaningless
    result set rather than an error. Measured on a live instance:
    ``equals 0`` matched 20,905 tickets (a LEFT-JOIN-NULL "has no actor"
    match), an empty value matched the entire 59,689-ticket baseline, and a
    non-numeric value returned the same arbitrary 3 rows whatever the
    string. Guarding at the boundary is what keeps this fix from
    reintroducing the class of bug it exists to remove.

    Parameters
    ----------
    value : int
        Candidate GLPI user identifier.
    parameter : str
        Name of the public parameter, used in the error message.

    Returns
    -------
    int
        The validated identifier.

    Raises
    ------
    GlpiValidationError
        When ``value`` is not a positive integer. ``bool`` is rejected
        explicitly because it is an ``int`` subclass in Python.
    """

    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise GlpiValidationError(
            f"{parameter} must be a positive integer GLPI user id; got "
            f"{value!r}. GLPI's v1 search silently returns unrelated rows "
            "for 0, empty or non-numeric actor values instead of failing."
        )
    return value


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
    """Custom statistics built on the contract API mixins."""

    async def _v1_ticket_ids_for_actor(
        self, user_id: int, *, search_options: tuple[int, ...], parameter: str
    ) -> set[int]:
        """Return ids of tickets linking ``user_id`` under any given role.

        Actor selection cannot be expressed in the v2 API, so this reads the
        v1 search engine, OR-ing one criterion per requested searchOption.
        Unlike v2 -- which silently ignores a filter field it does not know
        and answers with the complete unfiltered set -- v1 rejects an
        unknown searchOption with HTTP 400, so a mistake here fails loudly.

        Parameters
        ----------
        user_id : int
            GLPI user identifier; validated by :func:`_validate_actor_id`.
        search_options : tuple[int, ...]
            v1 searchOption ids to OR together, e.g.
            ``(_V1_SO_ASSIGNEE, _V1_SO_REQUESTER)``.
        parameter : str
            Public parameter name quoted in validation errors.

        Returns
        -------
        set[int]
            Ticket identifiers visible to the configured v1 session.

        Raises
        ------
        GlpiValidationError
            When ``user_id`` is not a positive integer.
        RuntimeError
            When the client has no v1 session configured.
        """

        uid = _validate_actor_id(user_id, parameter)
        v1 = self._require_v1_session("actor-based ticket statistics")

        params: dict[str, object] = {"forcedisplay[0]": _V1_SO_TICKET_ID}
        for index, option in enumerate(search_options):
            if index:
                params[f"criteria[{index}][link]"] = "OR"
            params[f"criteria[{index}][field]"] = option
            params[f"criteria[{index}][searchtype]"] = "equals"
            params[f"criteria[{index}][value]"] = uid

        ids: set[int] = set()
        start = 0
        while True:
            page = dict(params)
            page["range"] = f"{start}-{start + _V1_SEARCH_PAGE_SIZE - 1}"
            payload = await v1.request_json("GET", "search/Ticket", params=page)
            if not isinstance(payload, dict):
                break
            rows = payload.get("data")
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    raw = row.get(str(_V1_SO_TICKET_ID))
                    if isinstance(raw, bool) or not isinstance(raw, (int, str)):
                        continue
                    try:
                        ids.add(int(raw))
                    except (TypeError, ValueError):
                        continue
            total = payload.get("totalcount")
            # Bound by totalcount: asking for a range that starts past the
            # end is an HTTP 400 on this API, not an empty page.
            if not isinstance(total, int):
                break
            start += _V1_SEARCH_PAGE_SIZE
            if start >= total:
                break
        return ids

    async def _v1_task_statistics(
        self, ticket_ids: list[int], *, since: date
    ) -> TaskStatisticsResult:
        """Aggregate tasks for ``ticket_ids`` with one bulk v1 sweep.

        Replaces the per-ticket fan-out for large ticket sets. The v2 API
        publishes tasks only under ``/Assistance/Ticket/{id}/Timeline/Task``,
        so aggregating N tickets costs N requests; the v1 ``TicketTask``
        collection returns whole rows -- including ``tickets_id`` -- and
        pages 1000 at a time.

        Note that v1 ``search/TicketTask`` is *not* usable here: its
        searchOptions expose the task's own id, content, category, date,
        privacy, technician, duration and state, but no parent ticket id,
        so results could not be attributed back to a ticket.

        Rows are swept newest-first and paging stops once a page predates
        ``since``. A task cannot be created before the ticket it belongs to,
        and every ticket under consideration was created on or after
        ``since``, so no relevant task is missed. The upper end is
        deliberately unbounded: a ticket created inside the window may still
        gain tasks long afterwards.

        The returned aggregate is identical to :meth:`get_task_statistics`
        for the same tickets -- v1 ``actiontime`` is v2 ``duration``, and v1
        ``users_id`` is the v2 task ``user`` (the author; the technician
        lives in ``users_id_tech``, which v2 does not expose). Rows are
        mapped into ``GetTicketTask`` and summarised by the same helper, so
        the two paths cannot drift apart.

        Parameters
        ----------
        ticket_ids : list[int]
            Tickets whose tasks should be aggregated.
        since : date
            Lower bound on task creation; the start of the caller's window.

        Returns
        -------
        TaskStatisticsResult
            Same shape and keys as :meth:`get_task_statistics`.

        Raises
        ------
        RuntimeError
            When the client has no v1 session configured.
        """

        v1 = self._require_v1_session("bulk task statistics")
        wanted = set(ticket_ids)
        cutoff = since.isoformat()
        tasks: list[GetTicketTask] = []
        start = 0
        while True:
            payload = await v1.request_json(
                "GET",
                "TicketTask",
                params={
                    "range": f"{start}-{start + _V1_TASK_PAGE_SIZE - 1}",
                    "sort": "date_creation",
                    "order": "DESC",
                },
            )
            if not isinstance(payload, list) or not payload:
                break
            oldest_seen: str | None = None
            for row in payload:
                if not isinstance(row, dict):
                    continue
                created = row.get("date_creation")
                if isinstance(created, str) and created:
                    oldest_seen = created
                ticket_id = row.get("tickets_id")
                if not isinstance(ticket_id, int) or ticket_id not in wanted:
                    continue
                author = row.get("users_id")
                duration = row.get("actiontime")
                tasks.append(
                    GetTicketTask(
                        id=row.get("id") if isinstance(row.get("id"), int) else None,
                        tickets_id=ticket_id,
                        duration=duration if isinstance(duration, int) else 0,
                        user=(
                            IdNameRef(id=author)
                            if isinstance(author, int) and author
                            else None
                        ),
                    )
                )
            if len(payload) < _V1_TASK_PAGE_SIZE:
                break
            if oldest_seen is not None and oldest_seen[:10] < cutoff:
                break
            start += _V1_TASK_PAGE_SIZE
        return _summarize_tasks(ticket_ids, tasks)

    async def get_ticket_statistics(
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
        GlpiValidationError
            If ``default_days < 1``, ``start_date`` / ``end_date`` is not a
            valid ISO date, or ``start_date`` is after ``end_date``.
        """

        start, end = _resolve_window(
            start_date=start_date,
            end_date=end_date,
            default_days=default_days,
        )

        entity_filter: str | None = None
        if entity_id is not None:
            entity_filter = f"entity.id=={entity_id}"
        elif entity_name is not None:
            name_filter = rsql_contains_filter("name", entity_name) or ""
            entities = await self.search_entities(  # type: ignore[attr-defined]
                rsql_filter=name_filter,
                limit=200,
            )
            if not entities:
                return {"entities": {}}
            entity_filter = rsql_any_filter(
                *(f"entity.id=={e.id}" for e in entities if e.id is not None)
            )
        date_filter = f"date_creation=ge={start.isoformat()};"
        date_filter += f"date_creation=le={end.isoformat()} 23:59:59"
        query = rsql_all_filter(
            date_filter,
            entity_filter,
            _LIVE_TICKETS,
            extra_filter,
        )
        tickets: list[GetTicket] = await self.search_tickets(  # type: ignore[attr-defined]
            rsql_filter=query or "",
            limit=200,
        )
        return _summarize_tickets(tickets)

    async def get_task_statistics(
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
            await self.list_ticket_tasks(ticket_id)  # type: ignore[attr-defined]
            for ticket_id in ticket_ids
        ]
        flattened: list[GetTicketTask] = [task for batch in results for task in batch]
        return _summarize_tasks(ticket_ids, flattened)

    async def get_task_durations(
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
        GlpiValidationError
            If ``default_days < 1``, ``start_date`` / ``end_date`` is not a
            valid ISO date, or ``start_date`` is after ``end_date``.
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
            entity_filter = f"entity.id=={entity_id}"
        elif entity_name is not None:
            name_filter = rsql_contains_filter("name", entity_name) or ""
            entities = await self.search_entities(  # type: ignore[attr-defined]
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
                *(f"entity.id=={e.id}" for e in entities if e.id is not None)
            )

        # ``user_id`` selects on the ticket's actors, which v2 cannot
        # express; resolve the id set through v1 and intersect below.
        actor_ticket_ids: set[int] | None = None
        if user_id is not None:
            actor_ticket_ids = await self._v1_ticket_ids_for_actor(
                user_id,
                search_options=(_V1_SO_ASSIGNEE, _V1_SO_REQUESTER),
                parameter="user_id",
            )
            if not actor_ticket_ids:
                return TaskDurationsResult(
                    start_date=start.isoformat(),
                    end_date=end.isoformat(),
                    total_duration=0,
                    task_count=0,
                    duration_by_user={},
                    duration_by_entity={},
                    tasks=None,
                )

        editor_filter: str | None = None
        if user_editor_id is not None:
            editor_filter = f"user_editor.id=={user_editor_id}"

        recipient_filter: str | None = None
        if user_recipient_id is not None:
            recipient_filter = f"user_recipient.id=={user_recipient_id}"

        rsql_filter = (
            rsql_all_filter(
                date_filter,
                entity_filter,
                editor_filter,
                recipient_filter,
                _LIVE_TICKETS,
                extra_filter,
            )
            or ""
        )

        ticket_ids: list[int] = []
        ticket_entity_map: dict[int, str] = {}
        async for batch in self.iter_search_tickets(  # type: ignore[attr-defined]
            rsql_filter,
            batch_size=200,
        ):
            for ticket in batch:
                if ticket.id is None:
                    continue
                if actor_ticket_ids is not None and ticket.id not in actor_ticket_ids:
                    continue
                ticket_ids.append(ticket.id)
                ticket_entity_map[ticket.id] = _entity_key(ticket.entity)

        # One bulk v1 sweep replaces the per-ticket fan-out once the ticket
        # set is big enough to pay for it; the aggregate is identical.
        if self._v1 is not None and len(ticket_ids) >= _V1_TASK_BULK_THRESHOLD:
            result = await self._v1_task_statistics(ticket_ids, since=start)
        else:
            result = await self.get_task_statistics(ticket_ids)
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
                for task in await self.list_ticket_tasks(int(tid)):  # type: ignore[attr-defined]
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

    async def get_user_activity(
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
        GlpiValidationError
            If none of ``user_id``, ``username``, ``realname``, or
            ``firstname`` are supplied, or if the supplied criteria match
            no GLPI users.
        """

        if all(v is None for v in (user_id, username, realname, firstname)):
            raise GlpiValidationError(
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
            matched_users = await self.search_users(  # type: ignore[attr-defined]
                rsql_filter=user_rsql,
                limit=200,
            )
            if not matched_users:
                raise GlpiValidationError("No users matched the supplied criteria")
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

        # The date window is resolved once for every user rather than once
        # per user per role. Previously each user drove two full pagings of
        # the corpus, and because the actor clause was silently dropped by
        # v2 both walks returned the same unfiltered window.
        window_filter = rsql_all_filter(date_range, _LIVE_TICKETS) or ""
        window_ids: set[int] = set()
        async for batch in self.iter_search_tickets(  # type: ignore[attr-defined]
            window_filter,
            batch_size=200,
        ):
            for ticket in batch:
                if ticket.id is not None:
                    window_ids.add(ticket.id)

        users_output: dict[str, UserActivityEntry] = {}
        for uid in resolved_user_ids:
            display_key = user_display_map.get(uid, str(uid))
            # Assignee and requester are counted separately, so they are
            # resolved as separate v1 id sets rather than one OR-ed query.
            tech_count = len(
                window_ids
                & await self._v1_ticket_ids_for_actor(
                    uid, search_options=(_V1_SO_ASSIGNEE,), parameter="user_id"
                )
            )
            recipient_count = len(
                window_ids
                & await self._v1_ticket_ids_for_actor(
                    uid, search_options=(_V1_SO_REQUESTER,), parameter="user_id"
                )
            )
            task_dur = await self.get_task_durations(
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

    Raises
    ------
    GlpiValidationError
        If ``default_days < 1``, ``start_date`` / ``end_date`` is not a
        valid ISO ``YYYY-MM-DD`` string, or ``start_date`` is after
        ``end_date``.
    """

    if default_days < 1:
        raise GlpiValidationError("default_days must be a positive integer")
    try:
        parsed_end = date.fromisoformat(end_date) if end_date else date.today()
    except ValueError as exc:
        raise GlpiValidationError(f"Invalid end_date: {end_date!r}") from exc
    try:
        parsed_start = (
            date.fromisoformat(start_date)
            if start_date
            else parsed_end - timedelta(days=default_days - 1)
        )
    except ValueError as exc:
        raise GlpiValidationError(f"Invalid start_date: {start_date!r}") from exc
    if parsed_start > parsed_end:
        raise GlpiValidationError("start_date must be less than or equal to end_date")
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
