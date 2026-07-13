"""GLPI ``KBCategory`` schemas for the ``/Knowledgebase/Category`` endpoints.

The field layout mirrors ``components.schemas.KBCategory`` from the GLPI
OpenAPI contract (2.3.0). Read-only contract fields (``id``,
``completename``, ``level``) are excluded from the request models.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef


class GetKBCategory(GlpiModel):
    """Response shape returned by ``GET /Knowledgebase/Category`` endpoints.

    Mirrors ``components.schemas.KBCategory``. ``completename`` and
    ``level`` are server-managed (``readOnly``).
    """

    id: int | None = None
    name: str | None = None
    completename: str | None = None
    comment: str | None = None
    entity: IdNameRef | None = None
    is_recursive: bool | None = None
    parent: IdNameRef | None = None
    level: int | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None


class PostKBCategory(GlpiModel):
    """Request body for ``POST /Knowledgebase/Category``.

    Read-only contract fields (``id``, ``completename``, ``level``) are
    excluded because the server rejects them on input.
    """

    name: str | None = None
    comment: str | None = None
    entity: IdNameRef | None = None
    is_recursive: bool | None = None
    parent: IdNameRef | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None


class PatchKBCategory(PostKBCategory):
    """Request body for ``PATCH /Knowledgebase/Category/{id}``.

    The contract uses the same ``KBCategory`` schema for create and
    partial-update bodies; ``PatchKBCategory`` is kept distinct so client
    mixins can express the intent of the operation explicitly.
    """


class DeleteKBCategory(GlpiModel):
    """Body for ``DELETE /Knowledgebase/Category/{id}``.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the category instead of moving
        the record to the GLPI trash.
    """

    force: bool | None = None


__all__ = [
    "DeleteKBCategory",
    "GetKBCategory",
    "PatchKBCategory",
    "PostKBCategory",
]
