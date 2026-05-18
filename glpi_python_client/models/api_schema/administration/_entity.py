"""GLPI ``Entity`` schemas for the ``/Administration/Entity`` endpoints.

The field layout mirrors ``components.schemas.Entity`` from the GLPI OpenAPI
contract. Read-only contract fields are excluded from request models.
"""

from __future__ import annotations

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef


class GetEntity(GlpiModel):
    """Response shape returned by ``GET /Administration/Entity`` endpoints.

    Mirrors ``components.schemas.Entity``. All fields are optional because
    the contract does not advertise a ``required`` array.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier (contract field ``id`` — ``ID``,
        ``readOnly``).
    name : str | None, optional
        Display name of the entity (contract field ``name`` — ``Name``).
    comment : str | None, optional
        Free-form comment associated with the entity (contract field
        ``comment`` — ``Comment``).
    completename : str | None, optional
        Full hierarchical path of the entity in dotted notation (contract
        field ``completename`` — ``Complete name``, ``readOnly``).
    parent : IdNameRef | None, optional
        Reference to the parent entity in the hierarchy (contract field
        ``parent`` — ``Parent entity``).
    level : int | None, optional
        Depth of the entity in the hierarchy tree (contract field
        ``level`` — ``Level``, ``readOnly``).
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
    intentionally excluded because the server rejects them on input.

    Parameters
    ----------
    name : str | None, optional
        Display name of the entity (contract field ``name`` — ``Name``).
    comment : str | None, optional
        Free-form comment associated with the entity (contract field
        ``comment`` — ``Comment``).
    parent : IdNameRef | None, optional
        Reference to the parent entity in the hierarchy (contract field
        ``parent`` — ``Parent entity``).
    """

    name: str | None = None
    comment: str | None = None
    parent: IdNameRef | None = None


class PatchEntity(PostEntity):
    """Request body for ``PATCH /Administration/Entity/{id}``.

    The contract uses the same ``Entity`` schema for create and
    partial-update bodies; ``PatchEntity`` is kept distinct so client
    mixins can express the intent of the operation explicitly.
    """


class DeleteEntity(GlpiModel):
    """Query parameters for ``DELETE /Administration/Entity/{id}``.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the entity instead of moving the
        record to the GLPI trash. When ``False`` or :data:`None`, the
        server applies its default soft-delete behaviour and the entity
        can still be restored.
    """

    force: bool | None = None


__all__ = ["DeleteEntity", "GetEntity", "PatchEntity", "PostEntity"]
