"""GLPI pending reasons: the v2 catalogue and the v1 per-ticket item.

A pause is ticket status ``4`` (Pending) plus at most one
``PendingReason_Item`` row linking the ticket to an entry of the
``PendingReason`` catalogue. The two halves live on different APIs:

* The catalogue is read from the v2 ``/Assistance/PendingReason`` routes
  (list and per-id). Its entries are configuration objects, so there is
  no create, update or delete here. Fields are ``id``, ``name``,
  ``entity``, ``is_recursive``, ``is_default``, ``followup_frequency``
  (seconds), ``followups_before_resolution``, ``comment`` and the
  template and calendar links.
* The ticket's item is handled through the legacy v1 API. The v2 route
  ``/Assistance/Ticket/{id}/PendingReason`` returns the item (404 when
  there is none) but its schema omits ``pendingreasons_id``: it tells
  that a ticket is paused with a reason, not which. No v2 route writes
  an item. The three ticket methods therefore need the v1 session and
  raise :class:`RuntimeError` without one.

Behaviour of the v1 item routes, as measured on a server exposing both
APIs:

* ``GET Ticket/{id}/PendingReason_Item`` returns a list of at most one
  row.
* ``POST PendingReason_Item`` creates the item (201). It changes neither
  the ticket status nor its timeline, and works whatever the status. A
  second POST for the same ticket answers 400 (duplicate key on
  ``items_id`` and ``itemtype``). The item does not copy the catalogue's
  ``followup_frequency``: an omitted frequency is stored as ``0``.
* ``PUT PendingReason_Item/{id}`` changes the reason and the
  frequencies. ``PUT Ticket/{id}`` with ``pendingreasons_id`` answers
  success and ignores the reason.
* ``DELETE PendingReason_Item/{id}`` removes the item and leaves the
  status at ``4``. Leaving status ``4`` (to solved, closed or processing)
  removes the item by itself.
* A reason id that is not in the catalogue is stored silently.
* The GLPI interface pauses through a followup (``POST ITILFollowup``
  with ``pending=1`` and ``pendingreasons_id``), which also adds a
  visible followup to the timeline. The methods here add none.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from glpi_python_client._async.clients.commons._constants import (
    PENDING_REASON_ENDPOINT,
    GlpiId,
)
from glpi_python_client._async.clients.commons._payloads import model_from_payload
from glpi_python_client._async.clients.commons._transport import TransportMixin
from glpi_python_client._errors import GlpiProtocolError
from glpi_python_client.models.api_schema.assistance._pending_reason import (
    PendingReason,
    PendingReasonItem,
)

_V1_FEATURE_LABEL = "pending reason helpers"
_ITEM_RESOURCE = "PendingReason_Item"
_TICKET_ITEMTYPE = "Ticket"


class PendingReasonMixin(TransportMixin):
    """Read the pending-reason catalogue and manage a ticket's pending reason."""

    async def list_pending_reasons(
        self,
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        skip_entity: bool = False,
    ) -> list[PendingReason]:
        """List the entries of the pending-reason catalogue (v2).

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
        limit : int, optional
            Maximum number of records returned by the GLPI server.
        start : int, optional
            Zero-based offset of the first record returned.
        skip_entity : bool, optional
            When ``True`` the ``GLPI-Entity`` header is omitted so the
            read spans every entity the caller has access to.

        Returns
        -------
        list[PendingReason]
            Catalogue entries matching the filter.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        params: dict[str, object] = {"limit": limit, "start": start}
        if rsql_filter:
            params["filter"] = rsql_filter
        return await self._resource_list(
            PENDING_REASON_ENDPOINT,
            PendingReason,
            params=params,
            skip_entity=skip_entity,
        )

    async def iter_pending_reasons(
        self,
        rsql_filter: str = "",
        *,
        batch_size: int = 50,
        skip_entity: bool = False,
    ) -> AsyncIterator[list[PendingReason]]:
        """Yield successive pages of the catalogue until exhausted.

        Pagination advances the ``start`` offset after each batch and stops
        when the server returns fewer items than ``batch_size``.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
        batch_size : int, optional
            Number of records requested per page (default 50).
        skip_entity : bool, optional
            When ``True`` the ``GLPI-Entity`` header is omitted.

        Yields
        ------
        list[PendingReason]
            One page per iteration. The last batch may be shorter than
            ``batch_size``.
        """

        start = 0
        while True:
            batch = await self.list_pending_reasons(
                rsql_filter,
                limit=batch_size,
                start=start,
                skip_entity=skip_entity,
            )
            if batch:
                yield batch
            if len(batch) < batch_size:
                break
            start += batch_size

    async def get_ticket_pending_reason(
        self, ticket_id: GlpiId
    ) -> PendingReasonItem | None:
        """Return the pending-reason item of one ticket, or ``None``.

        Reads the legacy v1 route ``Ticket/{id}/PendingReason_Item``, the
        only one that carries the catalogue id (``pendingreasons_id``).
        An empty list means the ticket has no item.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the ticket.

        Returns
        -------
        PendingReasonItem | None
            The ticket's item, or ``None`` when it has none.

        Raises
        ------
        RuntimeError
            If the client has no v1 session (``v1_base_url`` and
            ``v1_user_token``).
        GlpiStatusError
            If the v1 server returns a non-success HTTP status.
        """

        v1 = self._require_v1_session(_V1_FEATURE_LABEL)
        endpoint = f"{_TICKET_ITEMTYPE}/{ticket_id}/{_ITEM_RESOURCE}"
        payload = await v1.request_json(
            "GET",
            endpoint,
            failure_message=f"Failed to read the pending reason of ticket {ticket_id}",
        )
        rows = payload if isinstance(payload, list) else []
        if not rows:
            return None
        return model_from_payload(
            PendingReasonItem, rows[0], server_timezone=self.server_timezone
        )

    async def set_ticket_pending_reason(
        self,
        ticket_id: GlpiId,
        reason_id: int,
        *,
        followup_frequency: int = 0,
        followups_before_resolution: int = 0,
    ) -> PendingReasonItem:
        """Link one ticket to a pending reason, creating or changing its item.

        The ticket's item is read first (v1 ``GET``). When one exists it is
        changed with ``PUT``; otherwise a new one is created with ``POST``,
        so the duplicate-key error is never provoked, and never parsed. The
        item is then read back and returned.

        This does **not** change the ticket status. The caller sets status
        ``4`` (Pending) itself, before or after. An item set on a ticket
        that is not pending is stored all the same, but has no effect on the
        ticket, and GLPI removes it by itself the next time the ticket
        leaves status ``4``. Setting a reason on a ticket that is already
        pending changes the reason without touching the status.

        The item does not copy the catalogue's ``followup_frequency``: pass
        the values wanted, or the item stores ``0``. A ``reason_id`` that is
        not in the catalogue is stored without error. The call adds nothing
        to the ticket timeline.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the ticket.
        reason_id : int
            Identifier of the catalogue entry, see :meth:`list_pending_reasons`.
        followup_frequency : int, optional
            Delay between automatic follow-ups, in seconds (default ``0``).
        followups_before_resolution : int, optional
            Number of automatic follow-ups before resolution (default ``0``).

        Returns
        -------
        PendingReasonItem
            The ticket's item after the write.

        Raises
        ------
        RuntimeError
            If the client has no v1 session (``v1_base_url`` and
            ``v1_user_token``).
        GlpiStatusError
            If the v1 server returns a non-success HTTP status.
        GlpiProtocolError
            If no item can be read back after a successful write.
        """

        v1 = self._require_v1_session(_V1_FEATURE_LABEL)
        existing = await self.get_ticket_pending_reason(ticket_id)
        if existing is not None and existing.id is not None:
            await v1.request_json(
                "PUT",
                f"{_ITEM_RESOURCE}/{existing.id}",
                json_body={
                    "input": {
                        "id": existing.id,
                        "pendingreasons_id": reason_id,
                        "followup_frequency": followup_frequency,
                        "followups_before_resolution": followups_before_resolution,
                    }
                },
                failure_message=(
                    f"Failed to update the pending reason of ticket {ticket_id}"
                ),
            )
        else:
            await v1.request_json(
                "POST",
                _ITEM_RESOURCE,
                json_body={
                    "input": {
                        "itemtype": _TICKET_ITEMTYPE,
                        "items_id": ticket_id,
                        "pendingreasons_id": reason_id,
                        "followup_frequency": followup_frequency,
                        "followups_before_resolution": followups_before_resolution,
                    }
                },
                failure_message=(
                    f"Failed to set the pending reason of ticket {ticket_id}"
                ),
            )
        item = await self.get_ticket_pending_reason(ticket_id)
        if item is None:
            raise GlpiProtocolError(
                f"GLPI stored no pending reason item for ticket {ticket_id} "
                "after the write"
            )
        return item

    async def clear_ticket_pending_reason(self, ticket_id: GlpiId) -> bool:
        """Remove the pending-reason item of one ticket, if it has one.

        Deletes the item through v1 ``DELETE PendingReason_Item/{id}``. The
        ticket status is left unchanged (a ticket cleared while at status
        ``4`` stays pending, without a reason). When the ticket has no item
        nothing is sent and ``False`` is returned.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the ticket.

        Returns
        -------
        bool
            ``True`` when an item was deleted, ``False`` when there was none.

        Raises
        ------
        RuntimeError
            If the client has no v1 session (``v1_base_url`` and
            ``v1_user_token``).
        GlpiStatusError
            If the v1 server returns a non-success HTTP status.
        """

        v1 = self._require_v1_session(_V1_FEATURE_LABEL)
        existing = await self.get_ticket_pending_reason(ticket_id)
        if existing is None or existing.id is None:
            return False
        await v1.request_json(
            "DELETE",
            f"{_ITEM_RESOURCE}/{existing.id}",
            failure_message=(
                f"Failed to clear the pending reason of ticket {ticket_id}"
            ),
        )
        return True


__all__ = ["PendingReasonMixin"]
