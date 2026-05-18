"""Asynchronous override for the statistics aggregation helper.

The async mixin overrides :meth:`get_task_statistics` so the per-ticket
task-listing calls are dispatched concurrently using
:func:`asyncio.gather`. ``get_ticket_statistics`` does not need a custom
override because it issues a single GLPI request and therefore behaves
correctly when wrapped by the bridge into a coroutine.
"""

from __future__ import annotations

import asyncio

from glpi_python_client.clients.custom._statistics import StatisticsMixin
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
    ) -> dict[str, object]:
        """Return task duration totals with concurrent per-ticket fetches.

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
            ``duration_by_ticket`` entries.
        """

        from glpi_python_client.clients.custom._statistics import _summarize_tasks

        if not ticket_ids:
            return {
                "ticket_count": 0,
                "task_count": 0,
                "total_duration": 0,
                "duration_by_user": {},
                "duration_by_ticket": {},
            }
        results = await asyncio.gather(
            *(
                self.list_ticket_tasks(ticket_id)  # type: ignore[attr-defined]
                for ticket_id in ticket_ids
            )
        )
        flattened: list[GetTicketTask] = [task for batch in results for task in batch]
        return _summarize_tasks(ticket_ids, flattened)


__all__ = ["AsyncStatisticsMixin"]
