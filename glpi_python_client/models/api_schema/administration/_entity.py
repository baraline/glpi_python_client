"""GLPI ``Entity`` schemas for the ``/Administration/Entity`` endpoints.

The field layout mirrors ``components.schemas.Entity`` from the GLPI OpenAPI
contract. Read-only contract fields are excluded from request models.
"""

from __future__ import annotations

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef


class GetEntity(GlpiModel):
    """Response shape returned by ``GET /Administration/Entity`` endpoints.

    Mirrors ``components.schemas.Entity``.
    """

    id: int | None = None
    name: str | None = None
    comment: str | None = None
    completename: str | None = None
    parent: IdNameRef | None = None
    level: int | None = None


class PostEntity(GlpiModel):
    """Request body for ``POST /Administration/Entity``.

    Read-only contract fields (``id``, ``completename``, ``level``) are
    intentionally excluded.
    """

    name: str | None = None
    comment: str | None = None
    parent: IdNameRef | None = None


class PatchEntity(PostEntity):
    """Request body for ``PATCH /Administration/Entity/{id}``."""


class DeleteEntity(GlpiModel):
    """Query parameters for ``DELETE /Administration/Entity/{id}``.

    Parameters
    ----------
    force : bool | None, optional
        Permanently delete the entity instead of moving it to the trash.
    """

    force: bool | None = None


__all__ = ["DeleteEntity", "GetEntity", "PatchEntity", "PostEntity"]
