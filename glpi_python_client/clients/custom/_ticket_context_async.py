"""Asynchronous override for the ticket-context aggregation helper.

The async mixin overrides :meth:`get_ticket_context` so the five
underlying GLPI calls are dispatched concurrently using
:func:`asyncio.gather`. The endpoint methods themselves are exposed as
coroutines by the
:class:`~glpi_python_client.clients.commons._async_bridge.AsyncBridge`
applied to :class:`~glpi_python_client.clients.AsyncGlpiClient`, so this
override simply awaits the bridge-wrapped versions concurrently.
"""

from __future__ import annotations

import asyncio

from glpi_python_client.clients.commons._constants import GlpiId
from glpi_python_client.clients.custom._ticket_context import TicketContextMixin
from glpi_python_client.models.custom_schema._ticket_context import GlpiTicketContext


class AsyncTicketContextMixin(TicketContextMixin):
    """Asynchronous ticket-context aggregation helper.

    The override calls the five underlying GLPI endpoint helpers, which
    the async bridge has wrapped as coroutines, and awaits them
    concurrently with :func:`asyncio.gather`. The async runtime keeps
    every concurrent worker on a distinct thread because the underlying
    HTTP layer is still backed by the blocking ``requests`` library.
    """

    async def get_ticket_context(  # type: ignore[override]
        self, ticket_id: GlpiId
    ) -> GlpiTicketContext:
        """Return one aggregated ticket context with concurrent fan-out.

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
        GlpiStatusError
            If any of the underlying GLPI calls returns a non-success
            HTTP status.
        """

        ticket, tasks, followups, solutions, documents = await asyncio.gather(
            self.get_ticket(ticket_id),  # type: ignore[attr-defined]
            self.list_ticket_tasks(ticket_id),  # type: ignore[attr-defined]
            self.list_ticket_followups(ticket_id),  # type: ignore[attr-defined]
            self.list_ticket_solutions(ticket_id),  # type: ignore[attr-defined]
            self.list_ticket_timeline_documents(  # type: ignore[attr-defined]
                ticket_id
            ),
        )
        return GlpiTicketContext(
            ticket=ticket,
            tasks=tasks,
            followups=followups,
            solutions=solutions,
            documents=documents,
        )


__all__ = ["AsyncTicketContextMixin"]
