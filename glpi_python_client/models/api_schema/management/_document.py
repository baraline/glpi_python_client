"""GLPI ``Document`` schemas for the ``/Management/Document`` endpoints.

The field layout mirrors ``components.schemas.Document`` from the GLPI
OpenAPI contract. Read-only contract fields (``id``, ``filepath``) are
excluded from request models. Binary uploads use the legacy multipart-form
gateway and remain handled by the client transport layer; this module only
covers the JSON metadata schema advertised by the contract.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef


class GetDocument(GlpiModel):
    """Response shape returned by ``GET /Management/Document`` endpoints.

    Mirrors ``components.schemas.Document``.
    """

    id: int | None = None
    name: str | None = None
    comment: str | None = None
    entity: IdNameRef | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    is_deleted: bool | None = None
    filename: str | None = None
    filepath: str | None = None
    mime: str | None = None
    sha1sum: str | None = None


class PostDocument(GlpiModel):
    """Request body for ``POST /Management/Document``."""

    name: str | None = None
    comment: str | None = None
    entity: IdNameRef | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    is_deleted: bool | None = None
    filename: str | None = None
    mime: str | None = None
    sha1sum: str | None = None


class PatchDocument(PostDocument):
    """Request body for ``PATCH /Management/Document/{id}``."""


class DeleteDocument(GlpiModel):
    """Query parameters for ``DELETE /Management/Document/{id}``.

    Parameters
    ----------
    force : bool | None, optional
        Permanently delete the document instead of moving it to the trash.
    """

    force: bool | None = None


__all__ = ["DeleteDocument", "GetDocument", "PatchDocument", "PostDocument"]
