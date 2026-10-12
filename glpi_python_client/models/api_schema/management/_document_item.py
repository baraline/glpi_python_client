"""GLPI ``Document_Item`` link rows, as the legacy v1 API returns them.

A ``Document_Item`` row links one document to one item: a ticket, a followup,
a task or a solution. The v1 sub-item route ``<Itemtype>/<id>/Document_Item``
answers a list of these rows. They are not the ``GetTimelineDocument`` shape
of the v2 timeline, which carries no entity and no dates.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema.enums import GlpiTimelinePosition


class GetDocumentItem(GlpiModel):
    """One ``Document_Item`` row linking a document to an item.

    Keys the model does not declare (``users_id``, ``is_recursive``,
    ``links`` and any plugin column) are kept in ``extra_payload``.

    Parameters
    ----------
    id : int
        Native identifier of the link row.
    documents_id : int
        Identifier of the linked document.
    itemtype : str | None, optional
        GLPI type of the item the document is linked to, for example
        ``"Ticket"`` or ``"ITILFollowup"``.
    items_id : int | None, optional
        Identifier of the item the document is linked to.
    entities_id : int | None, optional
        Identifier of the entity owning the link.
    date_creation : datetime | None, optional
        Creation timestamp of the link row.
    date_mod : datetime | None, optional
        Last modification timestamp of the link row.
    date : datetime | None, optional
        Timestamp GLPI records on the link.
    timeline_position : GlpiTimelinePosition | None, optional
        Position of the link in the ticket timeline. A link at
        :attr:`GlpiTimelinePosition.NO_TIMELINE` (``-1``) is written by
        GLPI's editor for an image it embeds in a text. Such a link is
        hidden from the ticket's Documents tab. A document uploaded as an
        attachment is linked at ``1``.
    """

    id: int
    documents_id: int
    itemtype: str | None = None
    items_id: int | None = None
    entities_id: int | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    date: datetime | None = None
    timeline_position: GlpiTimelinePosition | None = None


__all__ = ["GetDocumentItem"]
