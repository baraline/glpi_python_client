"""GLPI ``ContractCost`` schemas for the ``/Management/Contract/{id}/Cost``
sub-resource.

The field layout mirrors ``components.schemas.ContractCost`` from the GLPI
OpenAPI contract. The read-only contract field (``id``) is excluded from
request models.

``date_begin`` and ``date_end`` are modelled as ``datetime.datetime``, not
``datetime.date``. This is the opposite choice from ``Contract.date_begin``
(the parent resource): the contract declares ``ContractCost``'s two date
fields with ``format: date-time``, whereas ``Contract.date_begin`` is
``format: date``. The asymmetry is real and comes from the contract itself,
not from an inconsistency in this client -- do not "fix" one to match the
other.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef


class GetContractCost(GlpiModel):
    """Response shape for ``GET /Management/Contract/{id}/Cost`` endpoints.

    Mirrors ``components.schemas.ContractCost``.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier (``readOnly``).
    contract : IdNameRef | None, optional
        Related contract reference, the parent of this cost line.
    name : str | None, optional
        Short display name of the cost line.
    comment : str | None, optional
        Free-form comment associated with the cost line.
    date_begin : datetime | None, optional
        Cost line start timestamp (``format: date-time``). Unlike
        ``Contract.date_begin``, which the contract declares with
        ``format: date``, this field carries a time-of-day component.
    date_end : datetime | None, optional
        Cost line end timestamp (``format: date-time``).
    cost : float | None, optional
        Monetary amount of the cost line.
    budget : IdNameRef | None, optional
        Related budget reference.
    entity : IdNameRef | None, optional
        Owning GLPI entity reference.
    is_recursive : bool | None, optional
        Whether the cost line is visible in sub-entities of ``entity``.
    """

    id: int | None = None
    contract: IdNameRef | None = None
    name: str | None = None
    comment: str | None = None
    date_begin: datetime | None = None
    date_end: datetime | None = None
    cost: float | None = None
    budget: IdNameRef | None = None
    entity: IdNameRef | None = None
    is_recursive: bool | None = None


class PostContractCost(GlpiModel):
    """Request body for ``POST /Management/Contract/{id}/Cost``.

    The read-only contract field (``id``) is intentionally excluded
    because the server rejects it on input.

    Parameters
    ----------
    contract : IdNameRef | None, optional
        Related contract reference, the parent of this cost line.
    name : str | None, optional
        Short display name of the cost line.
    comment : str | None, optional
        Free-form comment associated with the cost line.
    date_begin : datetime | None, optional
        Cost line start timestamp to set (``format: date-time``). Unlike
        ``Contract.date_begin``, which the contract declares with
        ``format: date``, this field carries a time-of-day component.
    date_end : datetime | None, optional
        Cost line end timestamp to set (``format: date-time``).
    cost : float | None, optional
        Monetary amount of the cost line.
    budget : IdNameRef | None, optional
        Related budget reference.
    entity : IdNameRef | None, optional
        Owning GLPI entity reference.
    is_recursive : bool | None, optional
        Whether the cost line should be visible in sub-entities of
        ``entity``.
    """

    contract: IdNameRef | None = None
    name: str | None = None
    comment: str | None = None
    date_begin: datetime | None = None
    date_end: datetime | None = None
    cost: float | None = None
    budget: IdNameRef | None = None
    entity: IdNameRef | None = None
    is_recursive: bool | None = None


class PatchContractCost(PostContractCost):
    """Request body for ``PATCH /Management/Contract/{id}/Cost/{cost_id}``.

    The contract uses the same ``ContractCost`` schema for create and
    partial-update bodies; ``PatchContractCost`` is kept distinct so client
    mixins can express the intent of the operation explicitly.
    """


class DeleteContractCost(GlpiModel):
    """Query parameters for ``DELETE /Management/Contract/{id}/Cost/{cost_id}``.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the cost line instead of moving
        the record to the GLPI trash. When ``False`` or :data:`None`, the
        server applies its default soft-delete behaviour and the cost line
        can still be restored.
    """

    force: bool | None = None


__all__ = [
    "DeleteContractCost",
    "GetContractCost",
    "PatchContractCost",
    "PostContractCost",
]
