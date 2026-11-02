"""GLPI ``/Assistance/Ticket`` mixin.

The mixin exposes search, fetch, create, update, and delete helpers for the
GLPI ticket resource using the ``api_schema`` Pydantic models.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from glpi_python_client._async.clients.commons._constants import TICKET_ENDPOINT, GlpiId
from glpi_python_client._async.clients.commons._payloads import (
    ensure_v1_write_accepted,
)
from glpi_python_client._async.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema.assistance._ticket import (
    DeleteTicket,
    GetTicket,
    PatchTicket,
    PostTicket,
)

_V1_TICKET_FEATURE_LABEL = "take-into-account writes"


class TicketMixin(TransportMixin):
    """CRUD helpers for ``/Assistance/Ticket``.

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
            ``sort`` query parameter, spelled ``field`` or ``field:direction``
            (e.g. ``"date_mod:desc"``). Measured against GLPI 11: a space
            before the direction answers **HTTP 400** ("Invalid property for
            sorting"), a bare ``field`` sorts *ascending*, and a separate
            ``order`` parameter is ignored.
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

    async def iter_search_tickets(
        self,
        rsql_filter: str = "",
        *,
        batch_size: int = 50,
        sort: str | None = None,
        fields: tuple[str, ...] = (),
    ) -> AsyncIterator[list[GetTicket]]:
        """Yield successive pages of GLPI tickets until exhausted.

        The generator drives pagination automatically by advancing the
        ``start`` offset after each batch. Iteration stops when the server
        returns fewer items than ``batch_size``, which signals the last page.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
            Empty by default, which lists every visible ticket.
        batch_size : int, optional
            Number of records requested per page (default 50). Acts as
            the ``limit`` parameter on each underlying
            :meth:`search_tickets` call.
        sort : str | None, optional
            ``sort`` query parameter forwarded to each page request,
            spelled ``field`` or ``field:direction`` (e.g. ``"date_mod:desc"``).
            A space before the direction answers HTTP 400.
        fields : tuple[str, ...], optional
            Restricted set of contract field names to request.

        Yields
        ------
        list[GetTicket]
            One page of tickets per iteration. The last yielded batch may
            be shorter than ``batch_size``.
        """

        start = 0
        while True:
            batch = await self.search_tickets(
                rsql_filter,
                limit=batch_size,
                start=start,
                sort=sort,
                fields=fields,
            )
            if batch:
                yield batch
            if len(batch) < batch_size:
                break
            start += batch_size

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
        GlpiStatusError
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
        GlpiStatusError
            If the HTTP status is not success.
        GlpiProtocolError
            If the create response is missing the ``id`` field.
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
        GlpiStatusError
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
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        await self._resource_delete(
            f"{TICKET_ENDPOINT}/{ticket_id}",
            failure_message=f"Failed to delete ticket {ticket_id}",
            log_message=f"GLPI API deleted ticket {ticket_id}",
            force=force,
            delete_model_cls=DeleteTicket,
        )

    async def change_ticket_take_into_account(
        self,
        ticket_id: GlpiId,
        *,
        take_into_account_date: datetime | None,
        take_into_account_duration: int,
        do_not_compute: bool = True,
        disable_notifications: bool = True,
    ) -> None:
        """Write the take-into-account stamp of one ticket.

        GLPI stamps ``take_into_account_date`` on the first write made by an
        account allowed to take a ticket into account (and when a group is
        assigned). The v2 ``Ticket`` schema exposes the date as read-only and
        silently ignores ``_do_not_compute_takeintoaccount``, so the write
        goes through the legacy v1 API, which requires
        ``v1_base_url``/``v1_user_token`` to be configured (pointing at the
        legacy ``apirest.php``). GLPI records the change in the ticket
        history either way.

        Parameters
        ----------
        ticket_id : int | str
            Identifier of the ticket.
        take_into_account_date : datetime | None
            New take-into-account instant (v1 ``takeintoaccountdate``), or
            ``None`` for no stamp. An aware value is converted to the
            server's clock; a naive one is taken to be on it already. GLPI
            writes ``null`` instead whenever the duration is ``0``.
        take_into_account_duration : int
            Seconds from creation to the take-into-account (v1
            ``takeintoaccount_delay_stat``). GLPI treats ``0`` as "not taken
            into account".
        do_not_compute : bool, optional
            ``True`` (the default) sends ``_do_not_compute_takeintoaccount``
            so GLPI keeps the values written. With ``False`` and a zero
            duration, an account allowed to take the ticket into account
            stamps it again with the current time in the same write.
        disable_notifications : bool, optional
            ``True`` (the default) sends ``_disablenotif``, which suppresses
            the "ticket updated" notification.

        Raises
        ------
        RuntimeError
            When no legacy v1 session is configured on the client.
        GlpiStatusError
            When the legacy API returns a non-success status.
        GlpiProtocolError
            When the legacy API answers that the update was refused.
        """

        v1 = self._require_v1_session(_V1_TICKET_FEATURE_LABEL)
        stamp: str | None = None
        if take_into_account_date is not None:
            if take_into_account_date.tzinfo is not None:
                take_into_account_date = take_into_account_date.astimezone(
                    self.server_timezone
                )
            stamp = take_into_account_date.strftime("%Y-%m-%d %H:%M:%S")
        update: dict[str, object] = {
            "id": int(ticket_id),
            "takeintoaccountdate": stamp,
            "takeintoaccount_delay_stat": take_into_account_duration,
        }
        # GLPI reads ``_disablenotif`` with isset(), so a False flag must be absent.
        if do_not_compute:
            update["_do_not_compute_takeintoaccount"] = True
        if disable_notifications:
            update["_disablenotif"] = True
        payload = await v1.request_json(
            "PUT",
            f"Ticket/{ticket_id}",
            json_body={"input": update},
            failure_message=(
                f"Failed to write the take-into-account stamp of ticket {ticket_id}"
            ),
        )
        ensure_v1_write_accepted(
            payload, f"Writing the take-into-account stamp of ticket {ticket_id}"
        )

    async def clear_ticket_take_into_account(
        self,
        ticket_id: GlpiId,
        *,
        do_not_compute: bool = True,
        disable_notifications: bool = True,
    ) -> None:
        """Clear the take-into-account stamp of one ticket.

        The stamp collapses the time-to-own statistic to nearly zero for a
        ticket a connector has just created and written to. This is
        :meth:`change_ticket_take_into_account` with a ``None`` date and a
        ``0`` duration, so it has the same v1 requirement.

        Parameters
        ----------
        ticket_id : int | str
            Identifier of the ticket.
        do_not_compute : bool, optional
            ``True`` (the default) keeps GLPI from stamping the ticket again
            in the same write. ``False`` lets an account allowed to take the
            ticket into account undo the clear at once.
        disable_notifications : bool, optional
            ``True`` (the default) suppresses the "ticket updated"
            notification.

        Raises
        ------
        RuntimeError
            When no legacy v1 session is configured on the client.
        GlpiStatusError
            When the legacy API returns a non-success status.
        GlpiProtocolError
            When the legacy API answers that the update was refused.
        """

        await self.change_ticket_take_into_account(
            ticket_id,
            take_into_account_date=None,
            take_into_account_duration=0,
            do_not_compute=do_not_compute,
            disable_notifications=disable_notifications,
        )


__all__ = ["TicketMixin"]
