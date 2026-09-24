"""GLPI ``Computer`` schemas for the ``/Assets/Computer`` endpoints.

The field layout mirrors ``components.schemas.Computer`` from the GLPI
OpenAPI contract. Four read-only contract fields (``id``, ``uuid``,
``last_inventory_update``, ``last_boot``) are excluded from request
models.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import (
    IdNameCompletenameRef,
    IdNameRef,
)


class GetComputer(GlpiModel):
    """Response shape returned by ``GET /Assets/Computer`` endpoints.

    Mirrors ``components.schemas.Computer``. No field carries a
    ``description`` in the OpenAPI contract; the parameter notes below
    reflect the field names, types and ``readOnly`` flags as advertised.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier (``readOnly``).
    name : str | None, optional
        Short display name of the computer.
    comment : str | None, optional
        Free-form comment associated with the computer.
    status : IdNameRef | None, optional
        Related status reference, see ``Dropdowns/State``.
    entity : IdNameCompletenameRef | None, optional
        Owning GLPI entity reference, including its completename.
    is_recursive : bool | None, optional
        Whether the computer is visible to child entities.
    manufacturer : IdNameRef | None, optional
        Related manufacturer reference.
    user : IdNameRef | None, optional
        Related user reference for the person the computer is assigned to.
    user_tech : IdNameRef | None, optional
        Related user reference for the technician in charge of the
        computer.
    contact : str | None, optional
        Free-form contact name associated with the computer.
    contact_num : str | None, optional
        Free-form contact phone number associated with the computer.
    serial : str | None, optional
        Manufacturer serial number.
    otherserial : str | None, optional
        Secondary inventory or asset-tag number.
    is_deleted : bool | None, optional
        Whether the computer has been moved to the GLPI trash.
    date_creation : datetime | None, optional
        Creation timestamp of the computer record (``format: date-time``).
    date_mod : datetime | None, optional
        Last modification timestamp of the computer record
        (``format: date-time``).
    location : IdNameRef | None, optional
        Related location reference.
    type : IdNameRef | None, optional
        Related computer type reference.
    model : IdNameRef | None, optional
        Related computer model reference.
    group : list[IdNameRef] | None, optional
        Related groups the computer belongs to. Unlike most foreign-key
        fields on this model, the contract declares this as an array
        rather than a single reference.
    group_tech : list[IdNameRef] | None, optional
        Related groups in charge of the computer. Also an array, for the
        same reason as ``group``.
    uuid : str | None, optional
        Hardware UUID reported by automatic inventory (``readOnly``).
    network : IdNameRef | None, optional
        Related network reference.
    autoupdatesystem : IdNameRef | None, optional
        Related reference to the inventory or synchronisation source that
        manages automatic updates for this computer.
    is_template : bool | None, optional
        Whether this record is a computer template rather than a live
        computer.
    template_name : str | None, optional
        Name of the computer template used to create new computers from
        this record.
    is_dynamic : bool | None, optional
        Whether this record is kept in sync by automatic inventory.
    ticket_tco : float | None, optional
        Total cost of ownership tracked against the computer.
    last_inventory_update : datetime | None, optional
        Timestamp of the last automatic inventory update (``readOnly``,
        ``format: date-time``).
    last_boot : datetime | None, optional
        Timestamp of the last reported boot (``readOnly``,
        ``format: date-time``).
    """

    id: int | None = None
    name: str | None = None
    comment: str | None = None
    status: IdNameRef | None = None
    entity: IdNameCompletenameRef | None = None
    is_recursive: bool | None = None
    manufacturer: IdNameRef | None = None
    user: IdNameRef | None = None
    user_tech: IdNameRef | None = None
    contact: str | None = None
    contact_num: str | None = None
    serial: str | None = None
    otherserial: str | None = None
    is_deleted: bool | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    location: IdNameRef | None = None
    type: IdNameRef | None = None
    model: IdNameRef | None = None
    group: list[IdNameRef] | None = None
    group_tech: list[IdNameRef] | None = None
    uuid: str | None = None
    network: IdNameRef | None = None
    autoupdatesystem: IdNameRef | None = None
    is_template: bool | None = None
    template_name: str | None = None
    is_dynamic: bool | None = None
    ticket_tco: float | None = None
    last_inventory_update: datetime | None = None
    last_boot: datetime | None = None


class PostComputer(GlpiModel):
    """Request body for ``POST /Assets/Computer``.

    Four read-only contract fields (``id``, ``uuid``,
    ``last_inventory_update``, ``last_boot``) are intentionally excluded
    because the server rejects them on input.

    Parameters
    ----------
    name : str | None, optional
        Short display name of the computer.
    comment : str | None, optional
        Free-form comment associated with the computer.
    status : IdNameRef | None, optional
        Related status reference, see ``Dropdowns/State``.
    entity : IdNameCompletenameRef | None, optional
        Owning GLPI entity reference, including its completename.
    is_recursive : bool | None, optional
        Whether the computer is visible to child entities.
    manufacturer : IdNameRef | None, optional
        Related manufacturer reference.
    user : IdNameRef | None, optional
        Related user reference for the person the computer is assigned to.
    user_tech : IdNameRef | None, optional
        Related user reference for the technician in charge of the
        computer.
    contact : str | None, optional
        Free-form contact name associated with the computer.
    contact_num : str | None, optional
        Free-form contact phone number associated with the computer.
    serial : str | None, optional
        Manufacturer serial number.
    otherserial : str | None, optional
        Secondary inventory or asset-tag number.
    is_deleted : bool | None, optional
        Whether the computer should be moved to the GLPI trash.
    date_creation : datetime | None, optional
        Creation timestamp to set on the computer record
        (``format: date-time``).
    date_mod : datetime | None, optional
        Last modification timestamp to set on the computer record
        (``format: date-time``).
    location : IdNameRef | None, optional
        Related location reference.
    type : IdNameRef | None, optional
        Related computer type reference.
    model : IdNameRef | None, optional
        Related computer model reference.
    group : list[IdNameRef] | None, optional
        Related groups the computer belongs to. Unlike most foreign-key
        fields on this model, the contract declares this as an array
        rather than a single reference.
    group_tech : list[IdNameRef] | None, optional
        Related groups in charge of the computer. Also an array, for the
        same reason as ``group``.
    network : IdNameRef | None, optional
        Related network reference.
    autoupdatesystem : IdNameRef | None, optional
        Related reference to the inventory or synchronisation source that
        manages automatic updates for this computer.
    is_template : bool | None, optional
        Whether this record is a computer template rather than a live
        computer.
    template_name : str | None, optional
        Name of the computer template used to create new computers from
        this record.
    is_dynamic : bool | None, optional
        Whether this record is kept in sync by automatic inventory.
    ticket_tco : float | None, optional
        Total cost of ownership tracked against the computer.
    """

    name: str | None = None
    comment: str | None = None
    status: IdNameRef | None = None
    entity: IdNameCompletenameRef | None = None
    is_recursive: bool | None = None
    manufacturer: IdNameRef | None = None
    user: IdNameRef | None = None
    user_tech: IdNameRef | None = None
    contact: str | None = None
    contact_num: str | None = None
    serial: str | None = None
    otherserial: str | None = None
    is_deleted: bool | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    location: IdNameRef | None = None
    type: IdNameRef | None = None
    model: IdNameRef | None = None
    group: list[IdNameRef] | None = None
    group_tech: list[IdNameRef] | None = None
    network: IdNameRef | None = None
    autoupdatesystem: IdNameRef | None = None
    is_template: bool | None = None
    template_name: str | None = None
    is_dynamic: bool | None = None
    ticket_tco: float | None = None


class PatchComputer(PostComputer):
    """Request body for ``PATCH /Assets/Computer/{id}``.

    The contract uses the same ``Computer`` schema for create and
    partial-update bodies; ``PatchComputer`` is kept distinct so client
    mixins can express the intent of the operation explicitly.
    """


class DeleteComputer(GlpiModel):
    """Query parameters for ``DELETE /Assets/Computer/{id}``.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the computer instead of moving
        the record to the GLPI trash. When ``False`` or :data:`None`,
        the server applies its default soft-delete behaviour and the
        computer can still be restored.
    """

    force: bool | None = None


__all__ = ["DeleteComputer", "GetComputer", "PatchComputer", "PostComputer"]
