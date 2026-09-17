"""GLPI ``Contract_Item`` schemas for the ``/Assets/Computer/{id}/Contract``
sub-resource.

The field layout mirrors ``components.schemas.Contract_Item`` from the GLPI
OpenAPI contract. The read-only contract field (``id``) is excluded from
request models.

``itemtype`` is declared in the contract as a free string (``maxLength:
100``) rather than an enum, so nothing here validates that it names an
actual GLPI asset type. Client mixins that link a contract to a specific
asset -- see ``ComputerMixin.link_computer_contract`` -- set ``itemtype``
and ``items_id`` themselves rather than trusting the caller-supplied
values on ``PostContractItem``/``PatchContractItem``, because a typo in a
free-string field would otherwise silently attach the link to the wrong
kind of object.
"""

from __future__ import annotations

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef


class GetContractItem(GlpiModel):
    """Response shape for ``GET /Assets/Computer/{id}/Contract`` endpoints.

    Mirrors ``components.schemas.Contract_Item``.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier (``readOnly``).
    contract : IdNameRef | None, optional
        Related contract reference.
    itemtype : str | None, optional
        GLPI itemtype of the linked asset (free string, ``maxLength:
        100``, not an enum in the contract).
    items_id : int | None, optional
        Native GLPI identifier of the linked asset.
    """

    id: int | None = None
    contract: IdNameRef | None = None
    itemtype: str | None = None
    items_id: int | None = None


class PostContractItem(GlpiModel):
    """Request body for ``POST /Assets/Computer/{id}/Contract``.

    The read-only contract field (``id``) is intentionally excluded
    because the server rejects it on input. Client mixins that link a
    contract to a specific asset overwrite ``itemtype`` and ``items_id``
    on the body they send, regardless of what is set here; see the module
    docstring.

    Parameters
    ----------
    contract : IdNameRef | None, optional
        Related contract reference.
    itemtype : str | None, optional
        GLPI itemtype of the linked asset (free string, ``maxLength:
        100``, not an enum in the contract).
    items_id : int | None, optional
        Native GLPI identifier of the linked asset.
    """

    contract: IdNameRef | None = None
    itemtype: str | None = None
    items_id: int | None = None


class PatchContractItem(PostContractItem):
    """Request body for ``PATCH /Assets/Computer/{id}/Contract/{link_id}``.

    The contract uses the same ``Contract_Item`` schema for create and
    partial-update bodies; ``PatchContractItem`` is kept distinct so
    client mixins can express the intent of the operation explicitly.
    """


class DeleteContractItem(GlpiModel):
    """Query parameters for ``DELETE .../Contract/{link_id}``.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the link instead of moving the
        record to the GLPI trash. When ``False`` or :data:`None`, the
        server applies its default soft-delete behaviour and the link can
        still be restored.
    """

    force: bool | None = None


__all__ = [
    "DeleteContractItem",
    "GetContractItem",
    "PatchContractItem",
    "PostContractItem",
]
