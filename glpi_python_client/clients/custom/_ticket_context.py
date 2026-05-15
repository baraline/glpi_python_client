"""Aggregated ticket context view assembled from API mixins.

The ticket context mixin composes the public ticket and ticket-timeline
helpers to return a single :class:`GlpiTicketContext` model carrying the
primary ticket together with its timeline records.
"""

from __future__ import annotations

import asyncio

from glpi_python_client.clients.commons._constants import GlpiId
from glpi_python_client.clients.commons._transport import AsyncTransportMixin
from glpi_python_client.models.custom_schema._ticket_context import GlpiTicketContext


class AsyncTicketContextMixin(AsyncTransportMixin):
    """Asynchronous ticket-context aggregation helper.

    The mixin assumes the consuming client also exposes the ticket and
    ticket-timeline helpers from :mod:`glpi_python_client.clients.api`.
    """

    async def get_ticket_context(self, ticket_id: GlpiId) -> GlpiTicketContext:
        """Return one aggregated ticket context view.

        The primary ticket fetch is dispatched together with the four
        timeline list calls using :func:`asyncio.gather` so they are
        awaited concurrently.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the ticket to assemble.

        Returns
        -------
        GlpiTicketContext
            Aggregated view bundling the primary ticket together with
            its tasks, followups, solutions, and timeline document
            links.

        Raises
        ------
        ValueError
            If any of the underlying GLPI calls returns a non-success
            HTTP status.
        """

        ticket, tasks, followups, solutions, documents = await asyncio.gather(
            self.get_ticket(ticket_id),  # type: ignore[attr-defined]
            self.list_ticket_tasks(ticket_id),  # type: ignore[attr-defined]
            self.list_ticket_followups(ticket_id),  # type: ignore[attr-defined]
            self.list_ticket_solutions(ticket_id),  # type: ignore[attr-defined]
            self.list_ticket_timeline_documents(ticket_id),  # type: ignore[attr-defined]
        )
        return GlpiTicketContext(
            ticket=ticket,
            tasks=tasks,
            followups=followups,
            solutions=solutions,
            documents=documents,
        )


__all__ = ["AsyncTicketContextMixin"]
