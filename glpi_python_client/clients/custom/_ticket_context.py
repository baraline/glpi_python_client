"""Aggregated ticket context view assembled from API mixins.

The ticket context mixin composes the public ticket and ticket-timeline
helpers to return a single :class:`GlpiTicketContext` model carrying the
primary ticket together with its timeline records.
"""

from __future__ import annotations

from glpi_python_client.clients.commons._constants import GlpiId
from glpi_python_client.clients.commons._transport import TransportMixin
from glpi_python_client.models.custom_schema._ticket_context import GlpiTicketContext


class TicketContextMixin(TransportMixin):
    """Synchronous ticket-context aggregation helper.

    The mixin assumes the consuming client also exposes the ticket and
    ticket-timeline helpers from :mod:`glpi_python_client.clients.api`.
    The five underlying calls are executed sequentially; the async
    variant under
    :mod:`glpi_python_client.clients.custom._ticket_context_async`
    overrides :meth:`get_ticket_context` to fan them out concurrently.
    """

    def get_ticket_context(self, ticket_id: GlpiId) -> GlpiTicketContext:
        """Return one aggregated ticket context view.

        The primary ticket fetch and the four timeline list calls are
        executed sequentially in this synchronous implementation.

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

        ticket = self.get_ticket(ticket_id)  # type: ignore[attr-defined]
        tasks = self.list_ticket_tasks(ticket_id)  # type: ignore[attr-defined]
        followups = self.list_ticket_followups(ticket_id)  # type: ignore[attr-defined]
        solutions = self.list_ticket_solutions(ticket_id)  # type: ignore[attr-defined]
        documents = self.list_ticket_timeline_documents(  # type: ignore[attr-defined]
            ticket_id
        )
        return GlpiTicketContext(
            ticket=ticket,
            tasks=tasks,
            followups=followups,
            solutions=solutions,
            documents=documents,
        )


__all__ = ["TicketContextMixin"]
