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

    Mirrors ``components.schemas.Document``. No field carries a
    ``description`` in the OpenAPI contract. The ``filepath`` field is
    server-managed (``readOnly``).

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier (``readOnly``).
    name : str | None, optional
        Display name of the document.
    comment : str | None, optional
        Free-form comment associated with the document.
    entity : IdNameRef | None, optional
        Reference to the owning GLPI entity.
    date_creation : datetime | None, optional
        Creation timestamp of the document record (``format: date-time``).
    date_mod : datetime | None, optional
        Last modification timestamp of the document record
        (``format: date-time``).
    is_deleted : bool | None, optional
        Whether the document has been moved to the trash.
    filename : str | None, optional
        Original file name of the uploaded file.
    filepath : str | None, optional
        Server-managed storage path of the file (``readOnly``).
    mime : str | None, optional
        MIME type of the uploaded file.
    sha1sum : str | None, optional
        SHA-1 checksum of the stored file, used for deduplication.
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
    """Request body for ``POST /Management/Document``.

    Read-only contract fields (``id``, ``filepath``) are intentionally
    excluded because the server rejects them on input.

    Parameters
    ----------
    name : str | None, optional
        Display name of the document.
    comment : str | None, optional
        Free-form comment associated with the document.
    entity : IdNameRef | None, optional
        Reference to the owning GLPI entity.
    date_creation : datetime | None, optional
        Creation timestamp to set on the document record
        (``format: date-time``).
    date_mod : datetime | None, optional
        Last modification timestamp to set on the document record
        (``format: date-time``).
    is_deleted : bool | None, optional
        Whether to create the document in the trashed state.
    filename : str | None, optional
        Original file name of the uploaded file.
    mime : str | None, optional
        MIME type of the uploaded file.
    sha1sum : str | None, optional
        SHA-1 checksum of the stored file, used for deduplication.
    """

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
    """Request body for ``PATCH /Management/Document/{id}``.

    The contract uses the same ``Document`` schema for create and
    partial-update bodies; ``PatchDocument`` is kept distinct so client
    mixins can express the intent of the operation explicitly.
    """


class DeleteDocument(GlpiModel):
    """Query parameters for ``DELETE /Management/Document/{id}``.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the document instead of moving
        the record to the GLPI trash. When ``False`` or :data:`None`,
        the server applies its default soft-delete behaviour and the
        document can still be restored.
    """

    force: bool | None = None


__all__ = ["DeleteDocument", "GetDocument", "PatchDocument", "PostDocument"]
