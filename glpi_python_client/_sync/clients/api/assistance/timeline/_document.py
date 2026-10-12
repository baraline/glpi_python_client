"""GLPI ``/Assistance/Ticket/{id}/Timeline/Document`` mixin.

The mixin exposes list, fetch, link, and unlink helpers for the timeline
document endpoint that links existing GLPI documents to a ticket.

Notes
-----
The live GLPI v2 server returns each entry of the list endpoint wrapped
in a ``{"type": "Document_Item", "item": {...}}`` envelope, even though
the OpenAPI contract documents a flat array of ``Document_Item``.  The
``item`` value is a full ``Document`` record (matching :class:`GetDocument`),
not a ``Document_Item`` link record — real behaviour wins over the contract.
:func:`list_ticket_timeline_documents` unwraps the envelope through the shared
``TransportMixin._resource_list`` helper and deserialises each inner object
as :class:`GetDocument`.
"""

from __future__ import annotations

import re

from glpi_python_client._sync._concurrency import gather
from glpi_python_client._sync.clients.commons._constants import (
    TICKET_ENDPOINT,
    TIMELINE_DOCUMENT_SUFFIX,
    GlpiId,
)
from glpi_python_client._sync.clients.commons._payloads import model_from_payload
from glpi_python_client._sync.clients.commons._transport import TransportMixin
from glpi_python_client._errors import GlpiValidationError
from glpi_python_client.models.api_schema.assistance.timeline._document import (
    DeleteTimelineDocument,
    PatchTimelineDocument,
    PostTimelineDocument,
)
from glpi_python_client.models.api_schema.management._document import GetDocument
from glpi_python_client.models.api_schema.management._document_item import (
    FollowupDocuments,
    GetDocumentItem,
)

_ITEM_DOCUMENT_RANGE = "0-999"
_ITEM_DOCUMENT_PAGE_SIZE = 1000
_ITEMTYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_V1_FEATURE_LABEL = "item document link listing"
_FOLLOWUP_ITEMTYPE = "ITILFollowup"


class TimelineDocumentMixin(TransportMixin):
    """CRUD helpers for the ticket document timeline endpoint."""

    def list_ticket_timeline_documents(
        self, ticket_id: GlpiId
    ) -> list[GetDocument]:
        """List all documents linked to one ticket timeline.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.

        Returns
        -------
        list[GetDocument]
            Document records returned by the GLPI server.  The live API
            wraps each entry in a ``{"type": "Document_Item", "item": {...}}``
            envelope whose ``item`` value is a full ``Document`` record; the
            envelope is unwrapped automatically.
        """

        return self._resource_list(
            f"{TICKET_ENDPOINT}/{ticket_id}/{TIMELINE_DOCUMENT_SUFFIX}",
            GetDocument,
            failure_message=(
                f"Failed to list timeline documents for ticket {ticket_id}"
            ),
            unwrap_envelope=True,
        )

    def list_item_documents(
        self, itemtype: str, items_id: GlpiId
    ) -> list[GetDocumentItem]:
        """List the document links of one item, over the legacy v1 API.

        Only the followup route (``itemtype="ITILFollowup"``) has been
        checked against a live server.  Other itemtypes are sent to the same
        v1 sub-route unchanged.

        Unlike :meth:`list_ticket_timeline_documents`, this call needs the
        legacy v1 session (``v1_base_url`` and ``v1_user_token``).  Without
        one it raises ``RuntimeError``.

        It returns link rows, not documents.  A caller resolves each
        ``documents_id`` with ``get_document``.

        The library does not filter private followups, tasks or solutions
        for the caller: every link the authenticated user can read is
        returned.

        GLPI's editor links an image pasted into a followup to the followup,
        not to the ticket.  A caller that wants such images therefore walks
        the ticket's followups and lists each one.

        Parameters
        ----------
        itemtype : str
            GLPI itemtype owning the links, for example ``"ITILFollowup"``.
            It must start with a letter and contain only letters, digits and
            underscores, because it is placed in the URL path.
        items_id : GlpiId
            Positive numeric identifier of the item.

        Returns
        -------
        list[GetDocumentItem]
            Link rows, with naive timestamps localised to the server
            timezone.  An empty answer gives an empty list.

        Raises
        ------
        RuntimeError
            If the client was built without a v1 session.
        GlpiValidationError
            If ``itemtype`` or ``items_id`` is invalid, if GLPI answers
            something other than a list or an empty body, or if it answers a
            full page of 1000 rows or more, which may be truncated.  A
            partial list is never returned.
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        v1 = self._require_v1_session(_V1_FEATURE_LABEL)
        if not _ITEMTYPE_PATTERN.fullmatch(itemtype):
            raise GlpiValidationError(
                f"itemtype must match {_ITEMTYPE_PATTERN.pattern!r}, got {itemtype!r}"
            )
        if items_id <= 0:
            raise GlpiValidationError(
                f"items_id must be a positive integer, got {items_id!r}"
            )
        payload = v1.request_json(
            "GET",
            f"{itemtype}/{items_id}/Document_Item",
            params={"range": _ITEM_DOCUMENT_RANGE},
            failure_message=(f"Failed to list document links of {itemtype} {items_id}"),
        )
        if isinstance(payload, dict) and not payload:
            return []
        if not isinstance(payload, list):
            raise GlpiValidationError(
                f"Unexpected document link answer for {itemtype} {items_id}: "
                f"{type(payload).__name__}"
            )
        if len(payload) >= _ITEM_DOCUMENT_PAGE_SIZE:
            raise GlpiValidationError(
                f"{itemtype} {items_id} returned {len(payload)} document links, "
                "a full page that may be truncated"
            )
        return [
            model_from_payload(
                GetDocumentItem, row, server_timezone=self.server_timezone
            )
            for row in payload
        ]

    def list_ticket_followup_documents(
        self, ticket_id: GlpiId, *, include_private: bool = False
    ) -> list[FollowupDocuments]:
        """List the document links of each followup of one ticket.

        GLPI's editor links an image pasted into a followup to the followup,
        not to the ticket. :meth:`list_ticket_timeline_documents` therefore
        never returns such an image, and this method does.

        Each entry holds the followup and its links, so a caller reads
        ``followup.is_private`` to classify every link without a second
        read. Only followups are walked: tasks and solutions are not.

        This call needs the legacy v1 session (``v1_base_url`` and
        ``v1_user_token``). Without one it raises ``RuntimeError``.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.
        include_private : bool, optional
            When false (the default), private followups and followups whose
            ``is_private`` flag is missing are dropped and not queried, so
            only what a requester can see is returned. A missing flag counts
            as private. When true, every followup is kept.

        Returns
        -------
        list[FollowupDocuments]
            One entry per kept followup, in ascending followup id, including
            a followup with no link (an empty ``documents`` list). A link row
            that does not name that followup as its item is dropped.

        Raises
        ------
        RuntimeError
            If the client was built without a v1 session.
        GlpiValidationError
            If a kept followup has no identifier, or if reading the links of
            a followup fails validation. A partial list is never returned.
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        self._require_v1_session(_V1_FEATURE_LABEL)
        followups = self.list_ticket_followups(ticket_id)  # type: ignore[attr-defined]
        kept = [
            followup
            for followup in followups
            if include_private or followup.is_private is False
        ]
        if any(followup.id is None for followup in kept):
            raise GlpiValidationError(
                f"A followup of ticket {ticket_id} has no id, "
                "so its document links cannot be read"
            )
        kept.sort(key=lambda followup: followup.id)
        link_lists = gather(
            *(
                self.list_item_documents(_FOLLOWUP_ITEMTYPE, followup.id)
                for followup in kept
            )
        )
        return [
            FollowupDocuments(
                followup=followup,
                documents=[
                    row
                    for row in rows
                    if row.itemtype == _FOLLOWUP_ITEMTYPE
                    and row.items_id == followup.id
                ],
            )
            for followup, rows in zip(kept, link_lists, strict=True)
        ]

    def get_ticket_timeline_document(
        self, ticket_id: GlpiId, document_link_id: GlpiId
    ) -> GetDocument:
        """Fetch one document linked to the ticket timeline by its document ID.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the parent ticket.
        document_link_id : GlpiId
            Numeric identifier of the linked document to retrieve.

        Returns
        -------
        GetDocument
            Validated document payload.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        return self._resource_get(
            f"{TICKET_ENDPOINT}/{ticket_id}/"
            f"{TIMELINE_DOCUMENT_SUFFIX}/{document_link_id}",
            GetDocument,
            failure_message=(
                f"Failed to get timeline document {document_link_id} on "
                f"ticket {ticket_id}"
            ),
        )

    def link_ticket_timeline_document(
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
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        GlpiProtocolError
            If the create response is missing the ``id`` field.
        """

        return self._resource_create(
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

    def update_ticket_timeline_document(
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
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        self._resource_update(
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

    def unlink_ticket_timeline_document(
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
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        self._resource_delete(
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


__all__ = ["TimelineDocumentMixin"]
