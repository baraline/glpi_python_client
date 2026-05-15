"""Asynchronous GLPI ``/Assistance/Ticket/{id}/Timeline/Document`` mixin.

The mixin exposes list, fetch, link, and unlink helpers for the timeline
document endpoint that links existing GLPI documents to a ticket.

Notes
-----
The live GLPI v2 server returns each entry of the list endpoint wrapped
in a ``{"type": "Document_Item", "item": {...}}`` envelope, even though
the OpenAPI contract documents a flat array of ``Document_Item``. Real
behaviour wins over the contract, so :func:`list_ticket_timeline_documents`
unwraps the envelope through the shared
:meth:`~glpi_python_client.clients.commons._transport.AsyncTransportMixin._resource_list`
helper and tolerates both shapes.
"""

from __future__ import annotations

from glpi_python_client.clients.commons._constants import (
    TICKET_ENDPOINT,
    TIMELINE_DOCUMENT_SUFFIX,
    GlpiId,
)
from glpi_python_client.clients.commons._transport import AsyncTransportMixin
from glpi_python_client.models.api_schema.assistance.timeline._document import (
    DeleteTimelineDocument,
    GetTimelineDocument,
    PatchTimelineDocument,
    PostTimelineDocument,
)


class AsyncTimelineDocumentMixin(AsyncTransportMixin):
    """Asynchronous CRUD helpers for the ticket document timeline endpoint."""

    async def list_ticket_timeline_documents(
        self, ticket_id: GlpiId
    ) -> list[GetTimelineDocument]:
        """List all timeline documents linked to one ticket.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.

        Returns
        -------
        list[GetTimelineDocument]
            Document links returned by the GLPI server, with the timeline
            envelope unwrapped where present.
        """

        return await self._resource_list(
            f"{TICKET_ENDPOINT}/{ticket_id}/{TIMELINE_DOCUMENT_SUFFIX}",
            GetTimelineDocument,
            failure_message=(
                f"Failed to list timeline documents for ticket {ticket_id}"
            ),
            unwrap_envelope=True,
        )

    async def get_ticket_timeline_document(
        self, ticket_id: GlpiId, document_link_id: GlpiId
    ) -> GetTimelineDocument:
        """Fetch one timeline document link by identifier.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.
        document_link_id : GlpiId
            Numeric identifier of the timeline document link to retrieve.

        Returns
        -------
        GetTimelineDocument
            Validated document-link payload.

        Raises
        ------
        ValueError
            If the GLPI server returns a non-success HTTP status.
        """

        return await self._resource_get(
            f"{TICKET_ENDPOINT}/{ticket_id}/"
            f"{TIMELINE_DOCUMENT_SUFFIX}/{document_link_id}",
            GetTimelineDocument,
            failure_message=(
                f"Failed to get timeline document {document_link_id} on "
                f"ticket {ticket_id}"
            ),
        )

    async def link_ticket_timeline_document(
        self, ticket_id: GlpiId, document_link: PostTimelineDocument
    ) -> int:
        """Link an existing GLPI document to one ticket timeline.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.
        document_link : PostTimelineDocument
            Request body describing the link (typically the timeline
            position; document and ticket identifiers are inferred from
            the URL).

        Returns
        -------
        int
            Identifier assigned by the GLPI server to the new link.

        Raises
        ------
        ValueError
            If the create response is missing ``id`` or returns a
            non-success HTTP status.
        """

        return await self._resource_create(
            f"{TICKET_ENDPOINT}/{ticket_id}/{TIMELINE_DOCUMENT_SUFFIX}",
            document_link,
            failure_message=(f"Failed to link timeline document on ticket {ticket_id}"),
            missing_message=(
                "GLPI timeline document link response did not include an ID"
            ),
            log_message_factory=(
                lambda new_id: (
                    f"GLPI API linked timeline document {new_id} on ticket {ticket_id}"
                )
            ),
        )

    async def update_ticket_timeline_document(
        self,
        ticket_id: GlpiId,
        document_link_id: GlpiId,
        document_link: PatchTimelineDocument,
    ) -> None:
        """Update one timeline document link with a partial body.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.
        document_link_id : GlpiId
            Numeric identifier of the timeline document link to update.
        document_link : PatchTimelineDocument
            Partial request body.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the GLPI server returns a non-success HTTP status.
        """

        await self._resource_update(
            f"{TICKET_ENDPOINT}/{ticket_id}/"
            f"{TIMELINE_DOCUMENT_SUFFIX}/{document_link_id}",
            document_link,
            failure_message=(
                f"Failed to update timeline document {document_link_id} on "
                f"ticket {ticket_id}"
            ),
            log_message=(
                f"GLPI API updated timeline document {document_link_id} on "
                f"ticket {ticket_id}"
            ),
        )

    async def unlink_ticket_timeline_document(
        self,
        ticket_id: GlpiId,
        document_link_id: GlpiId,
        *,
        force: bool | None = None,
    ) -> None:
        """Unlink one timeline document from a ticket.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.
        document_link_id : GlpiId
            Numeric identifier of the timeline document link to remove.
        force : bool | None, optional
            When ``True`` the link is permanently deleted instead of
            being moved to the trash.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the GLPI server returns a non-success HTTP status.
        """

        await self._resource_delete(
            f"{TICKET_ENDPOINT}/{ticket_id}/"
            f"{TIMELINE_DOCUMENT_SUFFIX}/{document_link_id}",
            failure_message=(
                f"Failed to unlink timeline document {document_link_id} on "
                f"ticket {ticket_id}"
            ),
            log_message=(
                f"GLPI API unlinked timeline document {document_link_id} on "
                f"ticket {ticket_id}"
            ),
            force=force,
            delete_model_cls=DeleteTimelineDocument,
        )


__all__ = ["AsyncTimelineDocumentMixin"]
