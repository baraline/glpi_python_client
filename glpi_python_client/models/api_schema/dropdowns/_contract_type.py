"""GLPI ``ContractType`` schemas for the ``/Dropdowns/ContractType`` endpoints.

The field layout mirrors ``components.schemas.ContractType`` from the GLPI
OpenAPI contract. The read-only contract field (``id``) is excluded from
request models.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.models._base import GlpiModel


class GetContractType(GlpiModel):
    """Response shape returned by ``GET /Dropdowns/ContractType`` endpoints.

    Mirrors ``components.schemas.ContractType``. No field carries a
    ``description`` in the OpenAPI contract; the parameter notes below
    reflect the field names, types and ``readOnly`` flags as advertised.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier (``readOnly``).
    name : str | None, optional
        Short display name of the contract type.
    comment : str | None, optional
        Free-form comment associated with the contract type.
    date_creation : datetime | None, optional
        Creation timestamp of the contract type record
        (``format: date-time``).
    date_mod : datetime | None, optional
        Last modification timestamp of the contract type record
        (``format: date-time``).
    """

    id: int | None = None
    name: str | None = None
    comment: str | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None


class PostContractType(GlpiModel):
    """Request body for ``POST /Dropdowns/ContractType``.

    The read-only contract field (``id``) is intentionally excluded
    because the server rejects it on input.

    Parameters
    ----------
    name : str | None, optional
        Short display name of the contract type.
    comment : str | None, optional
        Free-form comment associated with the contract type.
    date_creation : datetime | None, optional
        Creation timestamp to set on the contract type record
        (``format: date-time``).
    date_mod : datetime | None, optional
        Last modification timestamp to set on the contract type record
        (``format: date-time``).
    """

    name: str | None = None
    comment: str | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None


class PatchContractType(PostContractType):
    """Request body for ``PATCH /Dropdowns/ContractType/{id}``.

    The contract uses the same ``ContractType`` schema for create and
    partial-update bodies; ``PatchContractType`` is kept distinct so client
    mixins can express the intent of the operation explicitly.
    """


class DeleteContractType(GlpiModel):
    """Query parameters for ``DELETE /Dropdowns/ContractType/{id}``.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the contract type instead of
        moving the record to the GLPI trash. When ``False`` or
        :data:`None`, the server applies its default soft-delete behaviour
        and the contract type can still be restored.
    """

    force: bool | None = None


__all__ = [
    "DeleteContractType",
    "GetContractType",
    "PatchContractType",
    "PostContractType",
]
