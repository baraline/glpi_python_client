"""Asynchronous overrides for the statistics aggregation helper.

The async mixin overrides :meth:`get_ticket_statistics`,
:meth:`get_task_statistics`, :meth:`get_task_durations`, and
:meth:`get_user_activity` so that every internal ``self.*`` call that
would otherwise be dispatched as a bridge-wrapped coroutine is properly
awaited. Without these overrides the bridge runs the synchronous mixin
bodies in a worker thread where the bridge-wrapped methods on ``self``
return unawaited coroutines instead of data, producing a
``RuntimeWarning: coroutine … was never awaited`` error.

:meth:`get_task_statistics` and :meth:`get_task_durations` additionally
dispatch their per-ticket ``list_ticket_tasks`` fan-outs concurrently
using :func:`asyncio.gather`.
"""

from __future__ import annotations

import asyncio

from glpi_python_client.clients.custom._statistics import (
    StatisticsMixin,
    TaskDurationsResult,
    TaskStatisticsResult,
    UserActivityResult,
    _entity_key,
    _summarize_tasks,
)
from glpi_python_client.models.api_schema.assistance.timeline._task import (
    GetTicketTask,
)


class AsyncStatisticsMixin(StatisticsMixin):
    """Asynchronous custom statistics with concurrent task fan-out.

    The override calls the bridge-wrapped ``list_ticket_tasks`` for each
    ticket identifier and awaits the resulting coroutines together via
    :func:`asyncio.gather`. Empty inputs return zeroed totals without
    any HTTP traffic.
    """

    async def get_task_statistics(  # type: ignore[override]
        self,
        ticket_ids: list[int],
    ) -> TaskStatisticsResult:
        """Return task duration totals with concurrent per-ticket fetches.

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
            ``duration_by_ticket`` entries.
        """

        if not ticket_ids:
            return TaskStatisticsResult(
                ticket_count=0,
                task_count=0,
                total_duration=0,
                duration_by_user={},
                duration_by_ticket={},
            )
        results = await asyncio.gather(
            *(
                self.list_ticket_tasks(ticket_id)  # type: ignore[attr-defined]
                for ticket_id in ticket_ids
            )
        )
        flattened: list[GetTicketTask] = [task for batch in results for task in batch]
        return _summarize_tasks(ticket_ids, flattened)

    async def get_task_durations(  # type: ignore[override]
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
        """Return task duration totals with concurrent per-ticket fetches.

        Overrides the synchronous implementation so that when
        ``return_task_details=True`` the per-ticket
        :meth:`list_ticket_tasks` calls are dispatched concurrently using
        :func:`asyncio.gather`. The date-window, entity, and user filter
        logic is identical to the synchronous version.

        Parameters
        ----------
        start_date : str | None, optional
            ISO ``YYYY-MM-DD`` start of the window.
        end_date : str | None, optional
            ISO ``YYYY-MM-DD`` end of the window.
        default_days : int, optional
            Span in days used when ``start_date`` is omitted (default 30).
        entity_id : int | None, optional
            Restrict to tickets in this entity.
        entity_name : str | None, optional
            Resolve entity by name and restrict to matched entities.
        user_id : int | None, optional
            Restrict to tickets where the user is assignee or requester.
        user_editor_id : int | None, optional
            Restrict to tickets last updated by this user.
        user_recipient_id : int | None, optional
            Restrict to tickets where this user is the requester.
        extra_filter : str | None, optional
            Optional raw RSQL fragment appended as an AND clause.
        return_task_details : bool, optional
            When ``True``, fan-out per-ticket task fetches concurrently
            and include a ``tasks`` list in the result.

        Returns
        -------
        TaskDurationsResult
            Same shape as the synchronous :meth:`get_task_durations`.
        """

        from collections import defaultdict

        from glpi_python_client.clients.commons._filters import (
            rsql_all_filter,
            rsql_any_filter,
            rsql_contains_filter,
        )
        from glpi_python_client.clients.custom._statistics import _resolve_window

        start, end = _resolve_window(
            start_date=start_date,
            end_date=end_date,
            default_days=default_days,
        )
        date_filter = (
            f"date_creation=ge={start.isoformat()};date_creation=le={end.isoformat()}"
        )

        entity_filter: str | None = None
        if entity_id is not None:
            entity_filter = f"entities_id=={entity_id}"
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
        async for batch in self.iter_search_tickets(  # type: ignore[attr-defined]
            rsql_filter,
            batch_size=200,
        ):
            for ticket in batch:
                if ticket.id is not None:
                    ticket_ids.append(ticket.id)
                    ticket_entity_map[ticket.id] = _entity_key(ticket.entity)

        result = await self.get_task_statistics(ticket_ids)

        duration_by_entity: defaultdict[str, int] = defaultdict(int)
        for tid, dur in result["duration_by_ticket"].items():
            entity_key = ticket_entity_map.get(int(tid), "unknown")
            duration_by_entity[entity_key] += int(dur)

        task_details: list[dict[str, object]] | None = None
        if return_task_details:
            tasks_per_ticket: list[list[GetTicketTask]] = await asyncio.gather(
                *(
                    self.list_ticket_tasks(int(tid))  # type: ignore[attr-defined]
                    for tid, dur in result["duration_by_ticket"].items()
                    if int(dur) > 0
                )
            )
            non_zero_tids = [
                int(tid)
                for tid, dur in result["duration_by_ticket"].items()
                if int(dur) > 0
            ]
            task_details = []
            for tid, tasks in zip(non_zero_tids, tasks_per_ticket, strict=True):
                for task in tasks:
                    task_details.append(
                        {
                            "task_id": task.id,
                            "ticket_id": tid,
                            "duration": int(task.duration or 0),
                            "user_id": task.user.id if task.user else None,
                            "user_name": task.user.name if task.user else None,
                            "date": str(task.date_creation or ""),
                        }
                    )

        return TaskDurationsResult(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            total_duration=result["total_duration"],
            task_count=result["task_count"],
            duration_by_user=result["duration_by_user"],
            duration_by_entity=dict(duration_by_entity),
            tasks=task_details,
        )

    async def get_ticket_statistics(  # type: ignore[override]
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

        Async override of :meth:`StatisticsMixin.get_ticket_statistics`.
        The synchronous base runs in a worker thread where ``self.search_tickets``
        and ``self.search_entities`` resolve to bridge-wrapped coroutines that
        would be silently dropped. This override awaits those calls directly on
        the event loop instead.

        Parameters
        ----------
        start_date : str | None, optional
            ISO ``YYYY-MM-DD`` start of the window.
        end_date : str | None, optional
            ISO ``YYYY-MM-DD`` end of the window. Defaults to today.
        default_days : int, optional
            Span in days used when ``start_date`` is omitted (default 30).
        entity_id : int | None, optional
            Restrict to tickets in this entity.
        entity_name : str | None, optional
            Resolve entity by name and restrict to matched entities.
        extra_filter : str | None, optional
            Optional raw RSQL fragment appended as an AND clause.

        Returns
        -------
        dict[str, object]
            Same shape as the synchronous :meth:`get_ticket_statistics`.

        Raises
        ------
        ValueError
            If ``default_days < 1`` or ``start_date > end_date``.
        """

        from glpi_python_client.clients.commons._filters import (
            rsql_all_filter,
            rsql_any_filter,
            rsql_contains_filter,
        )
        from glpi_python_client.clients.custom._statistics import (
            _resolve_window,
            _summarize_tickets,
        )

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
            entities = await self.search_entities(  # type: ignore[attr-defined]
                rsql_filter=name_filter,
                limit=200,
            )
            if not entities:
                return {"entities": {}}
            entity_filter = rsql_any_filter(
                *(f"entities_id=={e.id}" for e in entities if e.id is not None)
            )

        query = rsql_all_filter(
            f"date_creation=ge={start.isoformat()};date_creation=le={end.isoformat()}",
            entity_filter,
            extra_filter,
        )
        tickets = await self.search_tickets(  # type: ignore[attr-defined]
            rsql_filter=query or "",
            limit=200,
        )
        return _summarize_tickets(tickets)

    async def get_user_activity(  # type: ignore[override]
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

        Async override of :meth:`StatisticsMixin.get_user_activity`. The
        synchronous base calls ``self.search_users``, ``self.iter_search_tickets``,
        and ``self.get_task_durations`` through ``self``, which on the async
        client resolve to bridge-wrapped coroutines. This override awaits those
        calls and uses ``async for`` on the async generator.

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
            ISO ``YYYY-MM-DD`` start of the activity window.
        end_date : str | None, optional
            ISO ``YYYY-MM-DD`` end of the activity window. Defaults to today.
        default_days : int, optional
            Span in days used when ``start_date`` is omitted (default 30).

        Returns
        -------
        UserActivityResult
            Same shape as the synchronous :meth:`get_user_activity`.

        Raises
        ------
        ValueError
            If none of ``user_id``, ``username``, ``realname``, or
            ``firstname`` are supplied, or if the supplied criteria match
            no GLPI users.
        """

        from glpi_python_client.clients.commons._filters import (
            rsql_all_filter,
            rsql_contains_filter,
        )
        from glpi_python_client.clients.custom._statistics import (
            UserActivityEntry,
            UserActivityResult,
            _merge_task_durations,
            _resolve_window,
        )

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
            matched_users = await self.search_users(  # type: ignore[attr-defined]
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

        date_range = (
            f"date_creation=ge={start.isoformat()};date_creation=le={end.isoformat()}"
        )

        users_output: dict[str, UserActivityEntry] = {}
        for uid in resolved_user_ids:
            display_key = user_display_map.get(uid, str(uid))
            tech_count = 0
            async for batch in self.iter_search_tickets(  # type: ignore[attr-defined]
                f"users_id_assign=={uid};{date_range}",
                batch_size=200,
            ):
                tech_count += len(batch)
            recipient_count = 0
            async for batch in self.iter_search_tickets(  # type: ignore[attr-defined]
                f"users_id_requester=={uid};{date_range}",
                batch_size=200,
            ):
                recipient_count += len(batch)
            task_dur = await self.get_task_durations(
                start_date=start_date,
                end_date=end_date,
                default_days=default_days,
                user_id=uid,
            )
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


__all__ = ["AsyncStatisticsMixin"]
