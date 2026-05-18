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
from glpi_python_client.models.api_schema._content import GlpiMarkdownContent
from glpi_python_client.models.api_schema.enums import GlpiTimelinePosition


class GetFollowup(GlpiModel):
    """Response shape returned by ``GET`` on ticket timeline followup endpoints.

    Mirrors ``components.schemas.Followup``. Most fields carry no
    ``description`` in the contract; ``content`` (``format: html``) and
    ``timeline_position`` are notable exceptions.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier of the followup (``readOnly``).
    itemtype : str | None, optional
        GLPI item type the followup belongs to, typically ``"Ticket"``.
    items_id : int | None, optional
        Identifier of the parent GLPI item.
    content : GlpiMarkdownContent
        Body of the followup exchanged as HTML over the wire
        (``format: html``); transparent Markdown conversion is applied
        on the model boundary. Defaults to :data:`None`.
    is_private : bool | None, optional
        Whether the followup is visible only to technicians.
    user : IdNameRef | None, optional
        Reference to the author of the followup.
    user_editor : IdNameRef | None, optional
        Reference to the user who last edited the followup.
    request_type : IdNameRef | None, optional
        Reference to the request type or channel of the followup (no
        contract description).
    date : datetime | None, optional
        Date the followup was written.
    date_creation : datetime | None, optional
        Creation timestamp of the followup record.
    date_mod : datetime | None, optional
        Last modification timestamp of the followup record.
    timeline_position : GlpiTimelinePosition | None, optional
        Horizontal position of the followup in the GLPI ticket timeline
        widget (contract field ``timeline_position`` — ``The position
        in the timeline``; enumeration: ``0`` No timeline, ``1`` Not
        set, ``2`` Left, ``3`` Mid left, ``4`` Mid right, ``5`` Right).
    source_item_id : int | None, optional
        Identifier of the source item that generated this followup, if
        any.
    source_of_item_id : int | None, optional
        Identifier of the item for which this followup is a source (no
        contract description).
    """

    id: int | None = None
    itemtype: str | None = None
    items_id: int | None = None
    content: GlpiMarkdownContent = None
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
    """Request body for ``POST`` on ticket timeline followup endpoints.

    Read-only contract field (``id``) is excluded. All other fields from
    ``components.schemas.Followup`` are writable.

    Parameters
    ----------
    itemtype : str | None, optional
        GLPI item type the followup belongs to, typically ``"Ticket"``.
    items_id : int | None, optional
        Identifier of the parent GLPI item.
    content : GlpiMarkdownContent
        Body of the followup; Markdown is converted to HTML on
        serialisation (``format: html``). Defaults to :data:`None`.
    is_private : bool | None, optional
        Whether the followup is visible only to technicians.
    user : IdNameRef | None, optional
        Reference to the author of the followup.
    user_editor : IdNameRef | None, optional
        Reference to the user who last edited the followup.
    request_type : IdNameRef | None, optional
        Reference to the request type or channel of the followup (no
        contract description).
    date : datetime | None, optional
        Date to assign to the followup.
    date_creation : datetime | None, optional
        Creation timestamp to set on the followup record.
    date_mod : datetime | None, optional
        Last modification timestamp to set on the followup record (no
        contract description).
    timeline_position : GlpiTimelinePosition | None, optional
        Horizontal position of the followup in the GLPI ticket timeline
        widget (contract field ``timeline_position`` — ``The position
        in the timeline``; enumeration: ``0`` No timeline, ``1`` Not
        set, ``2`` Left, ``3`` Mid left, ``4`` Mid right, ``5`` Right).
    source_item_id : int | None, optional
        Identifier of the source item that generated this followup, if
        any.
    source_of_item_id : int | None, optional
        Identifier of the item for which this followup is a source (no
        contract description).
    """

    itemtype: str | None = None
    items_id: int | None = None
    content: GlpiMarkdownContent = None
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
    """Request body for ``PATCH`` on ticket timeline followup endpoints.

    Inherits all fields from :class:`PostFollowup`.
    """


class DeleteFollowup(GlpiModel):
    """Query parameters for ``DELETE`` on ticket timeline followup endpoints.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the followup instead of moving
        the record to the GLPI trash. When ``False`` or :data:`None`,
        the server applies its default soft-delete behaviour and the
        followup can still be restored.
    """

    force: bool | None = None


__all__ = ["DeleteFollowup", "GetFollowup", "PatchFollowup", "PostFollowup"]
