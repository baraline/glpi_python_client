"""GLPI ``Contract`` schemas for the ``/Management/Contract`` endpoints.

The field layout mirrors ``components.schemas.Contract`` from the GLPI
OpenAPI contract. The read-only contract field (``id``) is excluded from
request models, and ``costs`` is excluded from both request models as well:
cost lines are written through their own ``ContractCost`` endpoints, so
this class only ever reads them back.

``date_begin`` is modelled as ``datetime.date`` rather than
``datetime.datetime``, because the contract declares it with
``format: date`` -- GLPI stores no time-of-day for a contract's start.
This is the opposite choice from ``ContractCost``'s own date fields, which
the contract declares with ``format: date-time`` and which are therefore
modelled as ``datetime``. The asymmetry is real
and comes from the contract, not from an inconsistency in this client: a
plain ``date`` also falls outside the server-clock conversion that
``models/_base.py`` applies to aware ``datetime`` values, so keeping
``date_begin`` a ``date`` protects it from a shift that could roll the
start date to the previous or next day.
"""

from __future__ import annotations

from datetime import date, datetime

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef, IdRef
from glpi_python_client.models.api_schema.enums import GlpiContractRenewalType


class GetContract(GlpiModel):
    """Response shape returned by ``GET /Management/Contract`` endpoints.

    Mirrors ``components.schemas.Contract``.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier (``readOnly``).
    name : str | None, optional
        Short display name of the contract.
    comment : str | None, optional
        Free-form comment associated with the contract.
    status : IdNameRef | None, optional
        Related contract status reference.
    entity : IdNameRef | None, optional
        Owning GLPI entity reference.
    date_creation : datetime | None, optional
        Creation timestamp of the contract record (``format: date-time``).
    date_mod : datetime | None, optional
        Last modification timestamp of the contract record
        (``format: date-time``).
    type : IdNameRef | None, optional
        Related contract type reference, see ``Dropdowns/ContractType``.
    is_deleted : bool | None, optional
        Whether the contract has been moved to the GLPI trash.
    costs : list[IdRef] | None, optional
        Related contract cost line references. Read-only on this client:
        cost lines are created and updated through their own
        ``ContractCost`` endpoints, never through this model.
    number : str | None, optional
        Contract reference number.
    location : IdNameRef | None, optional
        Related location reference.
    date_begin : date | None, optional
        Contract start date (``format: date``). A plain calendar date, not
        a timestamp: GLPI stores no time-of-day here, and keeping it a
        ``date`` also keeps it out of the server-clock conversion applied
        to aware timestamps.
    duration : int | None, optional
        Contract duration, in months.
    notice_period : int | None, optional
        Notice period, in months.
    renewal_period : int | None, optional
        Renewal period, in months.
    invoice_period : int | None, optional
        Invoice period, in months.
    accounting_number : str | None, optional
        Accounting reference number.
    week_begin_hour : str | None, optional
        Weekday coverage start time, in ``HH:MM:SS`` format (RFC 3339
        partial-time).
    week_end_hour : str | None, optional
        Weekday coverage end time, in ``HH:MM:SS`` format (RFC 3339
        partial-time).
    saturday_begin_hour : str | None, optional
        Saturday coverage start time, in ``HH:MM:SS`` format (RFC 3339
        partial-time).
    saturday_end_hour : str | None, optional
        Saturday coverage end time, in ``HH:MM:SS`` format (RFC 3339
        partial-time).
    sunday_begin_hour : str | None, optional
        Sunday coverage start time, in ``HH:MM:SS`` format (RFC 3339
        partial-time).
    sunday_end_hour : str | None, optional
        Sunday coverage end time, in ``HH:MM:SS`` format (RFC 3339
        partial-time).
    use_saturday : bool | None, optional
        Whether the Saturday coverage hours apply to this contract.
    use_sunday : bool | None, optional
        Whether the Sunday coverage hours apply to this contract.
    max_links_allowed : int | None, optional
        Maximum number of items that can be linked to this contract
        (``0`` means unlimited).
    alert : int | None, optional
        Selects which expiration alerts are active. The contract is
        self-inconsistent about the last two values: the field's
        ``enum`` lists ``[0, 4, 8, 12, 64, 72]``, but its accompanying
        description numbers the same six meanings as ``0`` no alert,
        ``4`` alert on end date, ``8`` alert on notice date, ``12``
        both, ``16`` periodic alert, ``24`` periodic alert and alert on
        notice date. The first four values agree between the two
        listings; the last two do not, and neither pairing has been
        confirmed against a live server. Read as a bitmask, the
        description's numbering is self-consistent on consecutive bits
        (``4``, ``8``, ``16``, with ``12 = 4 + 8`` and ``24 = 8 + 16``),
        while the enum's ``64`` and ``72`` skip two bits with nothing
        occupying them -- that asymmetry is why this is left open
        rather than resolved. Left as a plain ``int`` rather than an
        enum so neither guess is hard-coded into the type.
    renewal_type : GlpiContractRenewalType | None, optional
        Renewal behaviour of the contract: no renewal, tacit (automatic)
        renewal, or explicit (manual) renewal.
    template_name : str | None, optional
        Name of the contract template used to create new contracts from
        this record.
    is_template : bool | None, optional
        Whether this record is a contract template rather than a live
        contract.
    """

    id: int | None = None
    name: str | None = None
    comment: str | None = None
    status: IdNameRef | None = None
    entity: IdNameRef | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    type: IdNameRef | None = None
    is_deleted: bool | None = None
    costs: list[IdRef] | None = None
    number: str | None = None
    location: IdNameRef | None = None
    date_begin: date | None = None
    duration: int | None = None
    notice_period: int | None = None
    renewal_period: int | None = None
    invoice_period: int | None = None
    accounting_number: str | None = None
    week_begin_hour: str | None = None
    week_end_hour: str | None = None
    saturday_begin_hour: str | None = None
    saturday_end_hour: str | None = None
    sunday_begin_hour: str | None = None
    sunday_end_hour: str | None = None
    use_saturday: bool | None = None
    use_sunday: bool | None = None
    max_links_allowed: int | None = None
    alert: int | None = None
    renewal_type: GlpiContractRenewalType | None = None
    template_name: str | None = None
    is_template: bool | None = None


class PostContract(GlpiModel):
    """Request body for ``POST /Management/Contract``.

    The read-only contract field (``id``) is intentionally excluded
    because the server rejects it on input. ``costs`` is also excluded:
    cost lines are written through their own ``ContractCost`` endpoints,
    never through this model.

    Parameters
    ----------
    name : str | None, optional
        Short display name of the contract.
    comment : str | None, optional
        Free-form comment associated with the contract.
    status : IdNameRef | None, optional
        Related contract status reference.
    entity : IdNameRef | None, optional
        Owning GLPI entity reference.
    date_creation : datetime | None, optional
        Creation timestamp to set on the contract record
        (``format: date-time``).
    date_mod : datetime | None, optional
        Last modification timestamp to set on the contract record
        (``format: date-time``).
    type : IdNameRef | None, optional
        Related contract type reference, see ``Dropdowns/ContractType``.
    is_deleted : bool | None, optional
        Whether the contract should be moved to the GLPI trash.
    number : str | None, optional
        Contract reference number.
    location : IdNameRef | None, optional
        Related location reference.
    date_begin : date | None, optional
        Contract start date (``format: date``). A plain calendar date, not
        a timestamp: GLPI stores no time-of-day here, and keeping it a
        ``date`` also keeps it out of the server-clock conversion applied
        to aware timestamps.
    duration : int | None, optional
        Contract duration, in months.
    notice_period : int | None, optional
        Notice period, in months.
    renewal_period : int | None, optional
        Renewal period, in months.
    invoice_period : int | None, optional
        Invoice period, in months.
    accounting_number : str | None, optional
        Accounting reference number.
    week_begin_hour : str | None, optional
        Weekday coverage start time, in ``HH:MM:SS`` format (RFC 3339
        partial-time).
    week_end_hour : str | None, optional
        Weekday coverage end time, in ``HH:MM:SS`` format (RFC 3339
        partial-time).
    saturday_begin_hour : str | None, optional
        Saturday coverage start time, in ``HH:MM:SS`` format (RFC 3339
        partial-time).
    saturday_end_hour : str | None, optional
        Saturday coverage end time, in ``HH:MM:SS`` format (RFC 3339
        partial-time).
    sunday_begin_hour : str | None, optional
        Sunday coverage start time, in ``HH:MM:SS`` format (RFC 3339
        partial-time).
    sunday_end_hour : str | None, optional
        Sunday coverage end time, in ``HH:MM:SS`` format (RFC 3339
        partial-time).
    use_saturday : bool | None, optional
        Whether the Saturday coverage hours apply to this contract.
    use_sunday : bool | None, optional
        Whether the Sunday coverage hours apply to this contract.
    max_links_allowed : int | None, optional
        Maximum number of items that can be linked to this contract
        (``0`` means unlimited).
    alert : int | None, optional
        Selects which expiration alerts are active. The contract is
        self-inconsistent about the last two values: the field's
        ``enum`` lists ``[0, 4, 8, 12, 64, 72]``, but its accompanying
        description numbers the same six meanings as ``0`` no alert,
        ``4`` alert on end date, ``8`` alert on notice date, ``12``
        both, ``16`` periodic alert, ``24`` periodic alert and alert on
        notice date. The first four values agree between the two
        listings; the last two do not, and neither pairing has been
        confirmed against a live server. Read as a bitmask, the
        description's numbering is self-consistent on consecutive bits
        (``4``, ``8``, ``16``, with ``12 = 4 + 8`` and ``24 = 8 + 16``),
        while the enum's ``64`` and ``72`` skip two bits with nothing
        occupying them -- that asymmetry is why this is left open
        rather than resolved. Left as a plain ``int`` rather than an
        enum so neither guess is hard-coded into the type.
    renewal_type : GlpiContractRenewalType | None, optional
        Renewal behaviour of the contract: no renewal, tacit (automatic)
        renewal, or explicit (manual) renewal.
    template_name : str | None, optional
        Name of the contract template used to create new contracts from
        this record.
    is_template : bool | None, optional
        Whether this record is a contract template rather than a live
        contract.
    """

    name: str | None = None
    comment: str | None = None
    status: IdNameRef | None = None
    entity: IdNameRef | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    type: IdNameRef | None = None
    is_deleted: bool | None = None
    number: str | None = None
    location: IdNameRef | None = None
    date_begin: date | None = None
    duration: int | None = None
    notice_period: int | None = None
    renewal_period: int | None = None
    invoice_period: int | None = None
    accounting_number: str | None = None
    week_begin_hour: str | None = None
    week_end_hour: str | None = None
    saturday_begin_hour: str | None = None
    saturday_end_hour: str | None = None
    sunday_begin_hour: str | None = None
    sunday_end_hour: str | None = None
    use_saturday: bool | None = None
    use_sunday: bool | None = None
    max_links_allowed: int | None = None
    alert: int | None = None
    renewal_type: GlpiContractRenewalType | None = None
    template_name: str | None = None
    is_template: bool | None = None


class PatchContract(PostContract):
    """Request body for ``PATCH /Management/Contract/{id}``.

    The contract uses the same ``Contract`` schema for create and
    partial-update bodies; ``PatchContract`` is kept distinct so client
    mixins can express the intent of the operation explicitly.
    """


class DeleteContract(GlpiModel):
    """Query parameters for ``DELETE /Management/Contract/{id}``.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the contract instead of moving
        the record to the GLPI trash. When ``False`` or :data:`None`, the
        server applies its default soft-delete behaviour and the contract
        can still be restored.
    """

    force: bool | None = None


__all__ = [
    "DeleteContract",
    "GetContract",
    "PatchContract",
    "PostContract",
]
