"""Synchronous GLPI ``/Assistance/Ticket/{id}/Timeline/Followup`` mixin.

The mixin exposes list, fetch, create, update, and delete helpers for the
ticket followup timeline endpoint, exchanging the ``api_schema`` followup
models with the GLPI API.

Notes
-----
The live GLPI v2 server returns each entry of the list endpoint wrapped
in a ``{"type": "ITILFollowup", "item": {...}}`` envelope, even though
the OpenAPI contract documents a flat array of ``ITILFollowup``. Real
behaviour wins over the contract, so :func:`list_ticket_followups`
unwraps the envelope via the shared
:meth:`~glpi_python_client.clients.commons._transport.TransportMixin._resource_list`
helper and tolerates both shapes.
"""

from __future__ import annotations

from glpi_python_client.clients.commons._constants import (
    FOLLOWUP_SUFFIX,
    TICKET_ENDPOINT,
    GlpiId,
)
from glpi_python_client.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema.assistance.timeline._followup import (
    DeleteFollowup,
    GetFollowup,
    PatchFollowup,
    PostFollowup,
)


class FollowupMixin(TransportMixin):
    """Synchronous CRUD helpers for the ticket followup timeline endpoint."""

    def list_ticket_followups(self, ticket_id: GlpiId) -> list[GetFollowup]:
        """List all followups linked to one ticket.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.

        Returns
        -------
        list[GetFollowup]
            Followups returned by the GLPI server, with the timeline
            envelope unwrapped where present.
        """

        return self._resource_list(
            f"{TICKET_ENDPOINT}/{ticket_id}/{FOLLOWUP_SUFFIX}",
            GetFollowup,
            failure_message=f"Failed to list followups for ticket {ticket_id}",
            unwrap_envelope=True,
        )

    def get_ticket_followup(
        self, ticket_id: GlpiId, followup_id: GlpiId
    ) -> GetFollowup:
        """Fetch one ticket followup by identifier.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.
        followup_id : GlpiId
            Numeric identifier of the followup to retrieve.

        Returns
        -------
        GetFollowup
            Validated followup payload.

        Raises
        ------
        ValueError
            If the GLPI server returns a non-success HTTP status.
        """

        return self._resource_get(
            f"{TICKET_ENDPOINT}/{ticket_id}/{FOLLOWUP_SUFFIX}/{followup_id}",
            GetFollowup,
            failure_message=(
                f"Failed to get followup {followup_id} on ticket {ticket_id}"
            ),
        )

    def create_ticket_followup(self, ticket_id: GlpiId, followup: PostFollowup) -> int:
        """Create one followup on a ticket.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.
        followup : PostFollowup
            Request body describing the followup to create.

        Returns
        -------
        int
            Identifier assigned by the GLPI server to the new followup.

        Raises
        ------
        ValueError
            If the create response is missing ``id`` or returns a
            non-success HTTP status.
        """

        return self._resource_create(
            f"{TICKET_ENDPOINT}/{ticket_id}/{FOLLOWUP_SUFFIX}",
            followup,
            failure_message=f"Failed to create followup on ticket {ticket_id}",
            missing_message="GLPI followup create response did not include an ID",
            id_keys=("id", "followup_id"),
            log_message_factory=(
                lambda new_id: (
                    f"GLPI API created followup {new_id} on ticket {ticket_id}"
                )
            ),
        )

    def update_ticket_followup(
        self,
        ticket_id: GlpiId,
        followup_id: GlpiId,
        followup: PatchFollowup,
    ) -> None:
        """Update one ticket followup with a partial body.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.
        followup_id : GlpiId
            Numeric identifier of the followup to update.
        followup : PatchFollowup
            Partial request body.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the GLPI server returns a non-success HTTP status.
        """

        self._resource_update(
            f"{TICKET_ENDPOINT}/{ticket_id}/{FOLLOWUP_SUFFIX}/{followup_id}",
            followup,
            failure_message=(
                f"Failed to update followup {followup_id} on ticket {ticket_id}"
            ),
            log_message=f"API updated followup {followup_id} on ticket {ticket_id}",
        )

    def delete_ticket_followup(
        self,
        ticket_id: GlpiId,
        followup_id: GlpiId,
        *,
        force: bool | None = None,
    ) -> None:
        """Delete one ticket followup by identifier.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.
        followup_id : GlpiId
            Numeric identifier of the followup to delete.
        force : bool | None, optional
            When ``True`` the followup is permanently deleted instead of
            being moved to the trash.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the GLPI server returns a non-success HTTP status.
        """

        self._resource_delete(
            f"{TICKET_ENDPOINT}/{ticket_id}/{FOLLOWUP_SUFFIX}/{followup_id}",
            failure_message=(
                f"Failed to delete followup {followup_id} on ticket {ticket_id}"
            ),
            log_message=f"API deleted followup {followup_id} on ticket {ticket_id}",
            force=force,
            delete_model_cls=DeleteFollowup,
        )


__all__ = ["FollowupMixin"]
