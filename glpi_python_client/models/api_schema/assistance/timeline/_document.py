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

    Mirrors ``components.schemas.Document_Item``.
    """

    id: int | None = None
    itemtype: str | None = None
    items_id: int | None = None
    documents_id: int | None = None
    filepath: str | None = None
    timeline_position: GlpiTimelinePosition | None = None


class PostTimelineDocument(GlpiModel):
    """Request body for ``POST`` on ticket timeline document endpoints."""

    timeline_position: GlpiTimelinePosition | None = None


class PatchTimelineDocument(PostTimelineDocument):
    """Request body for ``PATCH`` on ticket timeline document endpoints."""


class DeleteTimelineDocument(GlpiModel):
    """Query parameters for ``DELETE`` on ticket timeline document endpoints.

    Parameters
    ----------
    force : bool | None, optional
        Permanently delete the link instead of moving it to the trash.
    """

    force: bool | None = None


__all__ = [
    "DeleteTimelineDocument",
    "GetTimelineDocument",
    "PatchTimelineDocument",
    "PostTimelineDocument",
]
