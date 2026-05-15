"""GLPI ``Location`` schemas for the ``/Dropdowns/Location`` endpoints.

The field layout mirrors ``components.schemas.Location`` from the GLPI
OpenAPI contract. Read-only contract fields (``id``, ``completename``,
``level``) are excluded from request models.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef


class GetLocation(GlpiModel):
    """Response shape returned by ``GET /Dropdowns/Location`` endpoints.

    Mirrors ``components.schemas.Location``.
    """

    id: int | None = None
    name: str | None = None
    completename: str | None = None
    code: str | None = None
    alias: str | None = None
    comment: str | None = None
    entity: IdNameRef | None = None
    is_recursive: bool | None = None
    parent: IdNameRef | None = None
    level: int | None = None
    room: str | None = None
    building: str | None = None
    address: str | None = None
    town: str | None = None
    postcode: str | None = None
    state: str | None = None
    country: str | None = None
    latitude: str | None = None
    longitude: str | None = None
    altitude: str | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None


class PostLocation(GlpiModel):
    """Request body for ``POST /Dropdowns/Location``."""

    name: str | None = None
    code: str | None = None
    alias: str | None = None
    comment: str | None = None
    entity: IdNameRef | None = None
    is_recursive: bool | None = None
    parent: IdNameRef | None = None
    room: str | None = None
    building: str | None = None
    address: str | None = None
    town: str | None = None
    postcode: str | None = None
    state: str | None = None
    country: str | None = None
    latitude: str | None = None
    longitude: str | None = None
    altitude: str | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None


class PatchLocation(PostLocation):
    """Request body for ``PATCH /Dropdowns/Location/{id}``."""


class DeleteLocation(GlpiModel):
    """Query parameters for ``DELETE /Dropdowns/Location/{id}``.

    Parameters
    ----------
    force : bool | None, optional
        Permanently delete the location instead of moving it to the trash.
    """

    force: bool | None = None


__all__ = ["DeleteLocation", "GetLocation", "PatchLocation", "PostLocation"]
