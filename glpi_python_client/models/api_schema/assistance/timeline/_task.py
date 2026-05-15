"""GLPI ``TicketTask`` schemas for the ticket timeline task endpoints.

The endpoints live under ``/Assistance/Ticket/{id}/Timeline/Task``. The
field layout mirrors ``components.schemas.TicketTask`` from the GLPI
OpenAPI contract.

Read-only contract fields (``id``, ``uuid``) are excluded from request
models. ``content`` is exchanged as HTML; HTML/Markdown conversion is left
to the client transport layer.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef
from glpi_python_client.models.api_schema.enums import (
    GlpiTaskState,
    GlpiTimelinePosition,
)


class GetTicketTask(GlpiModel):
    """Response shape returned by ``GET`` on ticket timeline task endpoints.

    Mirrors ``components.schemas.TicketTask``.
    """

    id: int | None = None
    uuid: str | None = None
    content: str | None = None
    is_private: bool | None = None
    user: IdNameRef | None = None
    user_editor: IdNameRef | None = None
    user_tech: IdNameRef | None = None
    group_tech: IdNameRef | None = None
    date: datetime | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    duration: int | None = None
    planned_begin: datetime | None = None
    planned_end: datetime | None = None
    state: GlpiTaskState | None = None
    category: IdNameRef | None = None
    timeline_position: GlpiTimelinePosition | None = None
    tickets_id: int | None = None
    source_item_id: int | None = None
    source_of_item_id: int | None = None


class PostTicketTask(GlpiModel):
    """Request body for ``POST`` on ticket timeline task endpoints."""

    content: str | None = None
    is_private: bool | None = None
    user: IdNameRef | None = None
    user_editor: IdNameRef | None = None
    user_tech: IdNameRef | None = None
    group_tech: IdNameRef | None = None
    date: datetime | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    duration: int | None = None
    planned_begin: datetime | None = None
    planned_end: datetime | None = None
    state: GlpiTaskState | None = None
    category: IdNameRef | None = None
    timeline_position: GlpiTimelinePosition | None = None
    tickets_id: int | None = None
    source_item_id: int | None = None
    source_of_item_id: int | None = None


class PatchTicketTask(PostTicketTask):
    """Request body for ``PATCH`` on ticket timeline task endpoints."""


class DeleteTicketTask(GlpiModel):
    """Query parameters for ``DELETE`` on ticket timeline task endpoints.

    Parameters
    ----------
    force : bool | None, optional
        Permanently delete the task instead of moving it to the trash.
    """

    force: bool | None = None


__all__ = [
    "DeleteTicketTask",
    "GetTicketTask",
    "PatchTicketTask",
    "PostTicketTask",
]
