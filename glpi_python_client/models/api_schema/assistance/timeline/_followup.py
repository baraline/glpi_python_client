"""GLPI ``Followup`` schemas for the ticket timeline followup endpoints.

The endpoints live under
``/Assistance/Ticket/{id}/Timeline/Followup``. The field layout mirrors
``components.schemas.Followup`` from the GLPI OpenAPI contract.

Read-only contract fields (``id``) are excluded from request models.
``content`` is exchanged as HTML; HTML/Markdown conversion is left to the
client transport layer.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef
from glpi_python_client.models.api_schema.enums import GlpiTimelinePosition


class GetFollowup(GlpiModel):
    """Response shape returned by ``GET`` on ticket timeline followup endpoints.

    Mirrors ``components.schemas.Followup``.
    """

    id: int | None = None
    itemtype: str | None = None
    items_id: int | None = None
    content: str | None = None
    is_private: bool | None = None
    user: IdNameRef | None = None
    user_editor: IdNameRef | None = None
    request_type: IdNameRef | None = None
    date: datetime | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    timeline_position: GlpiTimelinePosition | None = None
    source_item_id: int | None = None
    source_of_item_id: int | None = None


class PostFollowup(GlpiModel):
    """Request body for ``POST`` on ticket timeline followup endpoints."""

    itemtype: str | None = None
    items_id: int | None = None
    content: str | None = None
    is_private: bool | None = None
    user: IdNameRef | None = None
    user_editor: IdNameRef | None = None
    request_type: IdNameRef | None = None
    date: datetime | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    timeline_position: GlpiTimelinePosition | None = None
    source_item_id: int | None = None
    source_of_item_id: int | None = None


class PatchFollowup(PostFollowup):
    """Request body for ``PATCH`` on ticket timeline followup endpoints."""


class DeleteFollowup(GlpiModel):
    """Query parameters for ``DELETE`` on ticket timeline followup endpoints.

    Parameters
    ----------
    force : bool | None, optional
        Permanently delete the followup instead of moving it to the trash.
    """

    force: bool | None = None


__all__ = ["DeleteFollowup", "GetFollowup", "PatchFollowup", "PostFollowup"]
