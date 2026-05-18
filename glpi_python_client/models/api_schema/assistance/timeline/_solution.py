"""GLPI ``Solution`` schemas for the ticket timeline solution endpoints.

The endpoints live under
``/Assistance/Ticket/{id}/Timeline/Solution``. The field layout mirrors
``components.schemas.Solution`` from the GLPI OpenAPI contract.

Read-only contract fields (``id``) are excluded from request models.
``content`` is exchanged as HTML; HTML/Markdown conversion is left to the
client transport layer.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef
from glpi_python_client.models.api_schema._content import GlpiMarkdownContent
from glpi_python_client.models.api_schema.enums import GlpiSolutionStatus


class GetSolution(GlpiModel):
    """Response shape returned by ``GET`` on ticket timeline solution endpoints.

    Mirrors ``components.schemas.Solution``. Most fields carry no
    ``description`` in the contract; ``status`` is a notable exception.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier of the solution (``readOnly``).
    itemtype : str | None, optional
        GLPI item type the solution belongs to, typically ``"Ticket"``.
    items_id : int | None, optional
        Identifier of the parent GLPI item.
    type : IdNameRef | None, optional
        Reference to the solution type.
    content : GlpiMarkdownContent
        Body of the solution exchanged as HTML over the wire
        (``format: html``); transparent Markdown conversion is applied
        on the model boundary. Defaults to :data:`None`.
    user : IdNameRef | None, optional
        Reference to the author of the solution.
    user_editor : IdNameRef | None, optional
        Reference to the user who last edited the solution.
    approver : IdNameRef | None, optional
        Reference to the user who approved or rejected the solution (no
        contract description).
    status : GlpiSolutionStatus | None, optional
        Approval state of the solution (contract field ``status`` —
        ``The status of the solution``; enumeration: ``1`` None,
        ``2`` Waiting, ``3`` Accepted, ``4`` Refused).
    approval_followup : IdNameRef | None, optional
        Reference to the followup generated when the solution was
        approved or rejected.
    date_creation : datetime | None, optional
        Creation timestamp of the solution record.
    date_mod : datetime | None, optional
        Last modification timestamp of the solution record.
    date_approval : datetime | None, optional
        Timestamp at which the solution was approved or rejected (no
        contract description).
    """

    id: int | None = None
    itemtype: str | None = None
    items_id: int | None = None
    type: IdNameRef | None = None
    content: GlpiMarkdownContent = None
    user: IdNameRef | None = None
    user_editor: IdNameRef | None = None
    approver: IdNameRef | None = None
    status: GlpiSolutionStatus | None = None
    approval_followup: IdNameRef | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    date_approval: datetime | None = None


class PostSolution(GlpiModel):
    """Request body for ``POST`` on ticket timeline solution endpoints.

    Read-only contract field (``id``) is excluded.

    Parameters
    ----------
    itemtype : str | None, optional
        GLPI item type the solution belongs to, typically ``"Ticket"``.
    items_id : int | None, optional
        Identifier of the parent GLPI item.
    type : IdNameRef | None, optional
        Reference to the solution type.
    content : GlpiMarkdownContent
        Body of the solution; Markdown is converted to HTML on
        serialisation (``format: html``). Defaults to :data:`None`.
    user : IdNameRef | None, optional
        Reference to the author of the solution.
    user_editor : IdNameRef | None, optional
        Reference to the user who last edited the solution.
    approver : IdNameRef | None, optional
        Reference to the user who approved or rejected the solution (no
        contract description).
    status : GlpiSolutionStatus | None, optional
        Approval state of the solution (contract field ``status`` —
        ``The status of the solution``; enumeration: ``1`` None,
        ``2`` Waiting, ``3`` Accepted, ``4`` Refused).
    approval_followup : IdNameRef | None, optional
        Reference to the followup generated when the solution was
        approved or rejected.
    date_creation : datetime | None, optional
        Creation timestamp to set on the solution record.
    date_mod : datetime | None, optional
        Last modification timestamp to set on the solution record (no
        contract description).
    date_approval : datetime | None, optional
        Timestamp at which the solution was approved or rejected (no
        contract description).
    """

    itemtype: str | None = None
    items_id: int | None = None
    type: IdNameRef | None = None
    content: GlpiMarkdownContent = None
    user: IdNameRef | None = None
    user_editor: IdNameRef | None = None
    approver: IdNameRef | None = None
    status: GlpiSolutionStatus | None = None
    approval_followup: IdNameRef | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    date_approval: datetime | None = None


class PatchSolution(PostSolution):
    """Request body for ``PATCH`` on ticket timeline solution endpoints.

    Inherits all fields from :class:`PostSolution`.
    """


class DeleteSolution(GlpiModel):
    """Query parameters for ``DELETE`` on ticket timeline solution endpoints.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the solution instead of moving
        the record to the GLPI trash. When ``False`` or :data:`None`,
        the server applies its default soft-delete behaviour and the
        solution can still be restored.
    """

    force: bool | None = None


__all__ = ["DeleteSolution", "GetSolution", "PatchSolution", "PostSolution"]
