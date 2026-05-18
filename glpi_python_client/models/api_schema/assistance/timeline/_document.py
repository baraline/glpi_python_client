"""GLPI ``Document_Item`` schemas for the ticket timeline document endpoints.

The endpoints live under
``/Assistance/Ticket/{id}/Timeline/Document``. The field layout mirrors
``components.schemas.Document_Item`` from the GLPI OpenAPI contract.

These models describe the link between a ticket and a stored document. The
underlying document object lives in :mod:`models.api_schema.management`.
Most ``Document_Item`` fields are read-only on the contract; the request
models therefore expose only the writable ``timeline_position`` slot.
"""

from __future__ import annotations

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema.enums import GlpiTimelinePosition


class GetTimelineDocument(GlpiModel):
    """Response shape returned by ``GET`` on ticket timeline document endpoints.

    Mirrors ``components.schemas.Document_Item``. Most fields are marked
    ``readOnly`` in the contract and are never accepted on write requests.
    Only ``timeline_position`` is writable.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier of the document-item link (``readOnly``).
    itemtype : str | None, optional
        GLPI item type the document is attached to (``readOnly``).
    items_id : int | None, optional
        Identifier of the parent GLPI item (``readOnly``).
    documents_id : int | None, optional
        Identifier of the referenced ``Document`` record (``readOnly``;
        no contract description).
    filepath : str | None, optional
        Server-managed storage path of the linked file (``readOnly``;
        no contract description).
    timeline_position : GlpiTimelinePosition | None, optional
        Horizontal position of the document in the GLPI ticket timeline
        widget (contract field ``timeline_position`` — ``The position
        in the timeline``; enumeration: ``0`` No timeline, ``1`` Not
        set, ``2`` Left, ``3`` Mid left, ``4`` Mid right, ``5`` Right).
    """

    id: int | None = None
    itemtype: str | None = None
    items_id: int | None = None
    documents_id: int | None = None
    filepath: str | None = None
    timeline_position: GlpiTimelinePosition | None = None


class PostTimelineDocument(GlpiModel):
    """Request body for ``POST`` on ticket timeline document endpoints.

    All read-only contract fields (``id``, ``itemtype``, ``items_id``,
    ``documents_id``, ``filepath``) are excluded; only the writable
    ``timeline_position`` field is exposed.

    Parameters
    ----------
    timeline_position : GlpiTimelinePosition | None, optional
        Horizontal position of the document in the GLPI ticket timeline
        widget (contract field ``timeline_position`` — ``The position
        in the timeline``; enumeration: ``0`` No timeline, ``1`` Not
        set, ``2`` Left, ``3`` Mid left, ``4`` Mid right, ``5`` Right).
    """

    timeline_position: GlpiTimelinePosition | None = None


class PatchTimelineDocument(PostTimelineDocument):
    """Request body for ``PATCH`` on ticket timeline document endpoints.

    Inherits the single writable field (``timeline_position``) from
    :class:`PostTimelineDocument`.
    """


class DeleteTimelineDocument(GlpiModel):
    """Query parameters for ``DELETE`` on ticket timeline document endpoints.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the document-item link instead
        of moving the record to the GLPI trash. When ``False`` or
        :data:`None`, the server applies its default soft-delete
        behaviour and the link can still be restored.
    """

    force: bool | None = None


__all__ = [
    "DeleteTimelineDocument",
    "GetTimelineDocument",
    "PatchTimelineDocument",
    "PostTimelineDocument",
]
