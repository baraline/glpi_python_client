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
from glpi_python_client.models.api_schema._content import GlpiMarkdownContent
from glpi_python_client.models.api_schema.enums import (
    GlpiTaskState,
    GlpiTimelinePosition,
)


class GetTicketTask(GlpiModel):
    """Response shape returned by ``GET`` on ticket timeline task endpoints.

    Mirrors ``components.schemas.TicketTask``. Several fields carry
    ``description`` values in the contract; others are documented by
    field name and type.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier of the task (``readOnly``).
    uuid : str | None, optional
        Server-generated universally unique identifier matching the
        pattern ``/^[0-9a-f]{8}-...-4...-[89ab]...-...$/i``
        (``readOnly``).
    content : GlpiMarkdownContent
        Body of the task exchanged as HTML over the wire
        (``format: html``); transparent Markdown conversion is applied
        on the model boundary. Defaults to :data:`None`.
    is_private : bool | None, optional
        Whether the task is visible only to technicians.
    user : IdNameRef | None, optional
        Reference to the author of the task.
    user_editor : IdNameRef | None, optional
        Reference to the user who last edited the task.
    user_tech : IdNameRef | None, optional
        Reference to the technician assigned to perform the task (no
        contract description).
    group_tech : IdNameRef | None, optional
        Reference to the group assigned to perform the task.
    date : datetime | None, optional
        Date the task was created.
    date_creation : datetime | None, optional
        Creation timestamp of the task record.
    date_mod : datetime | None, optional
        Last modification timestamp of the task record.
    duration : int | None, optional
        Time spent on the task in seconds.
    planned_begin : datetime | None, optional
        Planned start date and time for the task.
    planned_end : datetime | None, optional
        Planned end date and time for the task.
    state : GlpiTaskState | None, optional
        Completion state of the task (contract field ``state`` — ``The
        state of the task``; enumeration: ``0`` Information, ``1`` To
        do, ``2`` Done).
    category : IdNameRef | None, optional
        Reference to the task category.
    timeline_position : GlpiTimelinePosition | None, optional
        Horizontal position of the task in the GLPI ticket timeline
        widget (contract field ``timeline_position`` — ``The position
        in the timeline``; enumeration: ``0`` No timeline, ``1`` Not
        set, ``2`` Left, ``3`` Mid left, ``4`` Mid right, ``5`` Right).
    tickets_id : int | None, optional
        Identifier of the parent ticket.
    source_item_id : int | None, optional
        Identifier of the source item that generated this task, if any
       .
    source_of_item_id : int | None, optional
        Identifier of the item for which this task is a source (no
        contract description).
    """

    id: int | None = None
    uuid: str | None = None
    content: GlpiMarkdownContent = None
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
    """Request body for ``POST`` on ticket timeline task endpoints.

    Read-only contract fields (``id``, ``uuid``) are excluded.

    Parameters
    ----------
    content : GlpiMarkdownContent
        Body of the task; Markdown is converted to HTML on serialisation
        (``format: html``). Defaults to :data:`None`.
    is_private : bool | None, optional
        Whether the task is visible only to technicians.
    user : IdNameRef | None, optional
        Reference to the author of the task.
    user_editor : IdNameRef | None, optional
        Reference to the user who last edited the task.
    user_tech : IdNameRef | None, optional
        Reference to the technician assigned to perform the task (no
        contract description).
    group_tech : IdNameRef | None, optional
        Reference to the group assigned to perform the task.
    date : datetime | None, optional
        Date to assign to the task.
    date_creation : datetime | None, optional
        Creation timestamp to set on the task record.
    date_mod : datetime | None, optional
        Last modification timestamp to set on the task record (no
        contract description).
    duration : int | None, optional
        Time spent on the task in seconds.
    planned_begin : datetime | None, optional
        Planned start date and time for the task.
    planned_end : datetime | None, optional
        Planned end date and time for the task.
    state : GlpiTaskState | None, optional
        Completion state of the task (contract field ``state`` — ``The
        state of the task``; enumeration: ``0`` Information, ``1`` To
        do, ``2`` Done).
    category : IdNameRef | None, optional
        Reference to the task category.
    timeline_position : GlpiTimelinePosition | None, optional
        Horizontal position of the task in the GLPI ticket timeline
        widget (contract field ``timeline_position`` — ``The position
        in the timeline``; enumeration: ``0`` No timeline, ``1`` Not
        set, ``2`` Left, ``3`` Mid left, ``4`` Mid right, ``5`` Right).
    tickets_id : int | None, optional
        Identifier of the parent ticket.
    source_item_id : int | None, optional
        Identifier of the source item that generated this task, if any
       .
    source_of_item_id : int | None, optional
        Identifier of the item for which this task is a source (no
        contract description).
    """

    content: GlpiMarkdownContent = None
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
    """Request body for ``PATCH`` on ticket timeline task endpoints.

    Inherits all fields from :class:`PostTicketTask`.
    """


class DeleteTicketTask(GlpiModel):
    """Query parameters for ``DELETE`` on ticket timeline task endpoints.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the task instead of moving the
        record to the GLPI trash. When ``False`` or :data:`None`, the
        server applies its default soft-delete behaviour and the task
        can still be restored.
    """

    force: bool | None = None


__all__ = [
    "DeleteTicketTask",
    "GetTicketTask",
    "PatchTicketTask",
    "PostTicketTask",
]
