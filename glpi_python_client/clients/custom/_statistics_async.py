"""Asynchronous override for the statistics aggregation helper.

The async mixin overrides :meth:`get_task_statistics` and
:meth:`get_task_durations` so the per-ticket task-listing calls are
dispatched concurrently using :func:`asyncio.gather`.
``get_ticket_statistics`` does not need a custom override because it issues
a single GLPI request and therefore behaves correctly when wrapped by the
bridge into a coroutine.
"""

from __future__ import annotations

import asyncio

from glpi_python_client.clients.custom._statistics import (
    StatisticsMixin,
    TaskDurationsResult,
    TaskStatisticsResult,
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


__all__ = ["AsyncStatisticsMixin"]
