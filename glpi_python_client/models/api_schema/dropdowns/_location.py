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

    Mirrors ``components.schemas.Location``. No field carries a
    ``description`` in the OpenAPI contract; the parameter notes below
    reflect the field names, types and ``readOnly`` flags as advertised.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier (``readOnly``).
    name : str | None, optional
        Short display name of the location.
    completename : str | None, optional
        Full hierarchical path of the location in dotted notation
        (``readOnly``).
    code : str | None, optional
        Short alphanumeric code assigned to the location.
    alias : str | None, optional
        Alternate name or alias for the location.
    comment : str | None, optional
        Free-form comment associated with the location.
    entity : IdNameRef | None, optional
        Reference to the owning GLPI entity.
    is_recursive : bool | None, optional
        Whether the location is visible to child entities.
    parent : IdNameRef | None, optional
        Reference to the parent location in the hierarchy.
    level : int | None, optional
        Depth of the location in the hierarchy tree (``readOnly``).
    room : str | None, optional
        Room identifier within the building.
    building : str | None, optional
        Building identifier.
    address : str | None, optional
        Street address of the location.
    town : str | None, optional
        Town or city name.
    postcode : str | None, optional
        Postal code.
    state : str | None, optional
        State, region or province.
    country : str | None, optional
        Country name.
    latitude : str | None, optional
        Geographic latitude coordinate.
    longitude : str | None, optional
        Geographic longitude coordinate.
    altitude : str | None, optional
        Altitude above sea level.
    date_creation : datetime | None, optional
        Creation timestamp of the location record
        (``format: date-time``).
    date_mod : datetime | None, optional
        Last modification timestamp of the location record
        (``format: date-time``).
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
    """Request body for ``POST /Dropdowns/Location``.

    Read-only contract fields (``id``, ``completename``, ``level``) are
    intentionally excluded because the server rejects them on input.

    Parameters
    ----------
    name : str | None, optional
        Short display name of the location.
    code : str | None, optional
        Short alphanumeric code assigned to the location.
    alias : str | None, optional
        Alternate name or alias for the location.
    comment : str | None, optional
        Free-form comment associated with the location.
    entity : IdNameRef | None, optional
        Reference to the owning GLPI entity.
    is_recursive : bool | None, optional
        Whether the location is visible to child entities.
    parent : IdNameRef | None, optional
        Reference to the parent location in the hierarchy.
    room : str | None, optional
        Room identifier within the building.
    building : str | None, optional
        Building identifier.
    address : str | None, optional
        Street address of the location.
    town : str | None, optional
        Town or city name.
    postcode : str | None, optional
        Postal code.
    state : str | None, optional
        State, region or province.
    country : str | None, optional
        Country name.
    latitude : str | None, optional
        Geographic latitude coordinate.
    longitude : str | None, optional
        Geographic longitude coordinate.
    altitude : str | None, optional
        Altitude above sea level.
    date_creation : datetime | None, optional
        Creation timestamp to set on the location record
        (``format: date-time``).
    date_mod : datetime | None, optional
        Last modification timestamp to set on the location record
        (``format: date-time``).
    """

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
    """Request body for ``PATCH /Dropdowns/Location/{id}``.

    The contract uses the same ``Location`` schema for create and
    partial-update bodies; ``PatchLocation`` is kept distinct so client
    mixins can express the intent of the operation explicitly.
    """


class DeleteLocation(GlpiModel):
    """Query parameters for ``DELETE /Dropdowns/Location/{id}``.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the location instead of moving
        the record to the GLPI trash. When ``False`` or :data:`None`,
        the server applies its default soft-delete behaviour and the
        location can still be restored.
    """

    force: bool | None = None


__all__ = ["DeleteLocation", "GetLocation", "PatchLocation", "PostLocation"]
