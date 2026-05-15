"""Asynchronous GLPI ``/Assistance/Ticket`` mixin.

The mixin exposes search, fetch, create, update, and delete helpers for the
GLPI ticket resource using the ``api_schema`` Pydantic models.
"""

from __future__ import annotations

from glpi_python_client.clients.commons._constants import TICKET_ENDPOINT, GlpiId
from glpi_python_client.clients.commons._transport import AsyncTransportMixin
from glpi_python_client.models.api_schema.assistance._ticket import (
    DeleteTicket,
    GetTicket,
    PatchTicket,
    PostTicket,
)


class AsyncTicketMixin(AsyncTransportMixin):
    """Asynchronous CRUD helpers for ``/Assistance/Ticket``.

    The helpers exchange the contract-aligned ``GetTicket``, ``PostTicket``,
    ``PatchTicket``, and ``DeleteTicket`` models with the GLPI API and let the
    server perform all field-level validation.
    """

    async def search_tickets(
        self,
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
        fields: tuple[str, ...] = (),
    ) -> list[GetTicket]:
        """Search GLPI tickets with an optional RSQL filter.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter
            (for example ``"name==hello"`` or ``"status==2"``). Empty by
            default, which lists every visible ticket.
        limit : int, optional
            Maximum number of records returned by the GLPI server in one
            request.
        start : int, optional
            Zero-based offset of the first record returned.
        sort : str | None, optional
            ``sort`` query parameter forwarded as-is, e.g. ``"date_mod desc"``.
        fields : tuple[str, ...], optional
            Restricted set of contract field names to request. Empty
            tuple lets the GLPI server pick its default field set.

        Returns
        -------
        list[GetTicket]
            Tickets matching the filter, validated against the contract
            ``Ticket`` schema.
        """

        params: dict[str, object] = {"limit": limit, "start": start}
        if rsql_filter:
            params["filter"] = rsql_filter
        if sort:
            params["sort"] = sort
        if fields:
            params["fields"] = ",".join(fields)
        return await self._resource_list(TICKET_ENDPOINT, GetTicket, params=params)

    async def get_ticket(self, ticket_id: GlpiId) -> GetTicket:
        """Fetch one GLPI ticket by identifier.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the ticket to retrieve.

        Returns
        -------
        GetTicket
            Validated ticket payload.

        Raises
        ------
        ValueError
            If the GLPI server returns a non-success HTTP status.
        """

        return await self._resource_get(
            f"{TICKET_ENDPOINT}/{ticket_id}",
            GetTicket,
            failure_message=f"Failed to get ticket {ticket_id}",
        )

    async def create_ticket(self, ticket: PostTicket) -> int:
        """Create one GLPI ticket.

        Parameters
        ----------
        ticket : PostTicket
            Request body describing the ticket to create. Any extra
            fields are forwarded verbatim through ``extra_payload``.

        Returns
        -------
        int
            Identifier assigned by the GLPI server to the new ticket.

        Raises
        ------
        ValueError
            If the create response is missing the ``id`` field or the
            HTTP status is not success.
        """

        return await self._resource_create(
            TICKET_ENDPOINT,
            ticket,
            failure_message="Failed to create ticket",
            missing_message="GLPI ticket create response did not include an ID",
            log_message_factory=lambda new_id: f"GLPI API created ticket {new_id}",
        )

    async def update_ticket(self, ticket_id: GlpiId, ticket: PatchTicket) -> None:
        """Update one GLPI ticket with a partial body.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the ticket to update.
        ticket : PatchTicket
            Partial request body. Only fields explicitly set are sent.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the GLPI server returns a non-success HTTP status.
        """

        await self._resource_update(
            f"{TICKET_ENDPOINT}/{ticket_id}",
            ticket,
            failure_message=f"Failed to update ticket {ticket_id}",
            log_message=f"GLPI API updated ticket {ticket_id}",
        )

    async def delete_ticket(
        self, ticket_id: GlpiId, *, force: bool | None = None
    ) -> None:
        """Delete one GLPI ticket by identifier.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the ticket to delete.
        force : bool | None, optional
            When ``True`` the GLPI server permanently removes the ticket
            instead of moving it to the trash. ``None`` omits the query
            parameter and uses the GLPI default behaviour.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the GLPI server returns a non-success HTTP status.
        """

        await self._resource_delete(
            f"{TICKET_ENDPOINT}/{ticket_id}",
            failure_message=f"Failed to delete ticket {ticket_id}",
            log_message=f"GLPI API deleted ticket {ticket_id}",
            force=force,
            delete_model_cls=DeleteTicket,
        )


__all__ = ["AsyncTicketMixin"]
