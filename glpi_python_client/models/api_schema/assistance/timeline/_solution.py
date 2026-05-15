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

    Mirrors ``components.schemas.Solution``.
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
    """Request body for ``POST`` on ticket timeline solution endpoints."""

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
    """Request body for ``PATCH`` on ticket timeline solution endpoints."""


class DeleteSolution(GlpiModel):
    """Query parameters for ``DELETE`` on ticket timeline solution endpoints.

    Parameters
    ----------
    force : bool | None, optional
        Permanently delete the solution instead of moving it to the trash.
    """

    force: bool | None = None


__all__ = ["DeleteSolution", "GetSolution", "PatchSolution", "PostSolution"]
