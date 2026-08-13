"""GLPI ``Ticket`` schemas for the ``/Assistance/Ticket`` endpoints.

The field layout mirrors ``components.schemas.Ticket`` from the GLPI OpenAPI
contract. Read-only fields (``id``, ``actiontime``, ``begin_waiting_date``,
``waiting_duration``, ``resolution_duration``, ``close_duration``,
``resolution_date``, ``take_into_account_date``,
``take_into_account_duration``, ``sla_waiting_duration``,
``ola_waiting_duration``, ``ola_ttr_begin_date``, ``ola_tto_begin_date``,
``internal_resolution_date``, ``internal_take_into_account_date``) are
excluded from the request models.

Ticket ``content`` is exchanged with GLPI as HTML (``format: html``). The
schema models the raw transport string; HTML/Markdown conversion belongs
to the client layer.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import (
    IdNameCompletenameRef,
    IdNameRef,
)
from glpi_python_client.models.api_schema._content import GlpiMarkdownContent
from glpi_python_client.models.api_schema.enums import (
    GlpiGlobalValidation,
    GlpiPriority,
    GlpiTicketStatus,
    GlpiTicketType,
)


class _TicketTeamMember(GlpiModel):
    """One inline team-member entry of the ``Ticket.team`` array.

    The contract does not provide per-field ``description`` values for
    this inline object. The parameters below are documented by field name
    and context.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier of the team-member link.
    name : str | None, optional
        Display name of the actor (typically the user or group name).
    type : str | None, optional
        GLPI actor type, such as ``"User"`` or ``"Group"``.
    role : str | None, optional
        Ticket role assigned to the actor, such as ``"Requester"``,
        ``"Observer"`` or ``"Assigned to"``.
    """

    id: int | None = None
    name: str | None = None
    type: str | None = None
    role: str | None = None


class GetTicket(GlpiModel):
    """Response shape returned by ``GET /Assistance/Ticket`` endpoints.

    Mirrors ``components.schemas.Ticket``. Fields marked ``readOnly`` in
    the contract are excluded from the write models.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier (``readOnly``).
    name : str | None, optional
        Title of the ticket.
    content : GlpiMarkdownContent
        Body of the ticket exchanged as HTML over the wire
        (``format: html``); transparent Markdown conversion is applied
        on the model boundary. Defaults to :data:`None`.
    user_recipient : IdNameRef | None, optional
        Reference to the user designated as the ticket recipient (no
        contract description).
    user_editor : IdNameRef | None, optional
        Reference to the user who last edited the ticket.
    is_deleted : bool | None, optional
        Whether the ticket has been moved to the trash.
    category : IdNameRef | None, optional
        Reference to the ITIL category of the ticket.
    location : IdNameRef | None, optional
        Reference to the location associated with the ticket.
    urgency : GlpiPriority | None, optional
        Urgency level (contract enumeration: ``1`` Very Low, ``2`` Low,
        ``3`` Medium, ``4`` High, ``5`` Very High).
    impact : GlpiPriority | None, optional
        Impact level (contract enumeration: ``1`` Very Low, ``2`` Low,
        ``3`` Medium, ``4`` High, ``5`` Very High).
    priority : GlpiPriority | None, optional
        Computed or manually overridden priority (contract enumeration:
        ``1`` Very Low, ``2`` Low, ``3`` Medium, ``4`` High,
        ``5`` Very High).
    actiontime : int | None, optional
        Total action time in seconds (``readOnly``).
    begin_waiting_date : datetime | None, optional
        Timestamp at which the ticket entered the pending state
        (``readOnly``).
    waiting_duration : int | None, optional
        Total waiting duration in seconds (contract field
        ``waiting_duration`` — ``Total waiting duration in seconds``,
        ``readOnly``).
    resolution_duration : int | None, optional
        Total resolution duration in seconds (contract field
        ``resolution_duration`` — ``Total resolution duration in
        seconds``, ``readOnly``).
    close_duration : int | None, optional
        Total close duration in seconds (contract field
        ``close_duration`` — ``Total close duration in seconds``,
        ``readOnly``).
    resolution_date : datetime | None, optional
        Timestamp at which the ticket was resolved (``readOnly``).
    date_creation : datetime | None, optional
        Creation timestamp of the ticket record.
    date_mod : datetime | None, optional
        Last modification timestamp of the ticket record.
    date : datetime | None, optional
        Opening date of the ticket.
    date_solve : datetime | None, optional
        Date the ticket was marked as solved.
    date_close : datetime | None, optional
        Date the ticket was closed.
    type : GlpiTicketType | None, optional
        Ticket category (contract field ``type`` — ``The type of the
        ticket``; enumeration: ``1`` Incident, ``2`` Request).
    external_id : str | None, optional
        Identifier assigned by an external system.
    request_type : IdNameRef | None, optional
        Reference to the request type or channel.
    take_into_account_date : datetime | None, optional
        Timestamp at which a technician first acknowledged the ticket
        (``readOnly``).
    take_into_account_duration : int | None, optional
        Total take-into-account duration in seconds (contract field
        ``take_into_account_duration`` — ``Total take into account
        duration in seconds``, ``readOnly``).
    sla_ttr : IdNameRef | None, optional
        SLA applied for time-to-resolve.
    sla_tto : IdNameRef | None, optional
        SLA applied for time-to-own.
    ola_ttr : IdNameRef | None, optional
        OLA applied for time-to-resolve.
    ola_tto : IdNameRef | None, optional
        OLA applied for time-to-own.
    sla_level_ttr : IdNameRef | None, optional
        SLA level escalation step for time-to-resolve.
    ola_level_ttr : IdNameRef | None, optional
        OLA level escalation step for time-to-resolve.
    sla_waiting_duration : int | None, optional
        Total SLA waiting duration in seconds (contract field
        ``sla_waiting_duration`` — ``Total SLA waiting duration in
        seconds``, ``readOnly``).
    ola_waiting_duration : int | None, optional
        Total OLA waiting duration in seconds (contract field
        ``ola_waiting_duration`` — ``Total OLA waiting duration in
        seconds``, ``readOnly``).
    ola_ttr_begin_date : datetime | None, optional
        Timestamp at which the OLA TTR clock started (``readOnly``).
    ola_tto_begin_date : datetime | None, optional
        Timestamp at which the OLA TTO clock started (``readOnly``).
    internal_resolution_date : datetime | None, optional
        Internal resolution date used for OLA computations (``readOnly``;
        no contract description).
    internal_take_into_account_date : datetime | None, optional
        Internal take-into-account date used for OLA computations
        (``readOnly``).
    global_validation : GlpiGlobalValidation | None, optional
        Aggregated validation status of the ticket (contract field
        ``global_validation`` — ``The global status of the
        validation``; enumeration: ``1`` None, ``2`` Waiting,
        ``3`` Accepted, ``4`` Refused).
    status : IdNameRef | None, optional
        Current ticket status as an id/name reference.
    entity : IdNameCompletenameRef | None, optional
        Reference to the GLPI entity that owns the ticket.
    team : list[_TicketTeamMember] | None, optional
        Inline list of actors assigned to the ticket.
    """

    id: int | None = None
    name: str | None = None
    content: GlpiMarkdownContent = None
    user_recipient: IdNameRef | None = None
    user_editor: IdNameRef | None = None
    is_deleted: bool | None = None
    category: IdNameRef | None = None
    location: IdNameRef | None = None
    urgency: GlpiPriority | None = None
    impact: GlpiPriority | None = None
    priority: GlpiPriority | None = None
    actiontime: int | None = None
    begin_waiting_date: datetime | None = None
    waiting_duration: int | None = None
    resolution_duration: int | None = None
    close_duration: int | None = None
    resolution_date: datetime | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    date: datetime | None = None
    date_solve: datetime | None = None
    date_close: datetime | None = None
    type: GlpiTicketType | None = None
    external_id: str | None = None
    request_type: IdNameRef | None = None
    take_into_account_date: datetime | None = None
    take_into_account_duration: int | None = None
    sla_ttr: IdNameRef | None = None
    sla_tto: IdNameRef | None = None
    ola_ttr: IdNameRef | None = None
    ola_tto: IdNameRef | None = None
    sla_level_ttr: IdNameRef | None = None
    ola_level_ttr: IdNameRef | None = None
    sla_waiting_duration: int | None = None
    ola_waiting_duration: int | None = None
    ola_ttr_begin_date: datetime | None = None
    ola_tto_begin_date: datetime | None = None
    internal_resolution_date: datetime | None = None
    internal_take_into_account_date: datetime | None = None
    global_validation: GlpiGlobalValidation | None = None
    status: IdNameRef | None = None
    entity: IdNameCompletenameRef | None = None
    team: list[_TicketTeamMember] | None = None


class PostTicket(GlpiModel):
    """Request body for ``POST /Assistance/Ticket``.

    Read-only contract fields are excluded, and so is ``status`` -- not
    because the contract marks it ``readOnly`` (it does, and it is wrong
    about that: see :class:`PatchTicket`) but because GLPI 11 *ignores*
    the field on create. Measured on a live instance: posting
    ``{"status": 4}`` answers ``201`` and the new ticket reads back as
    ``New``. Declaring it here would publish a create argument that does
    nothing.

    Parameters
    ----------
    name : str | None, optional
        Title of the ticket.
    content : GlpiMarkdownContent
        Body of the ticket; Markdown is converted to HTML on
        serialisation (``format: html``). Defaults to :data:`None`.
    is_deleted : bool | None, optional
        Whether to create the ticket in the trashed state.
    category : IdNameRef | None, optional
        Reference to the ITIL category of the ticket.
    location : IdNameRef | None, optional
        Reference to the location associated with the ticket.
    urgency : GlpiPriority | None, optional
        Urgency level (contract enumeration: ``1`` Very Low, ``2`` Low,
        ``3`` Medium, ``4`` High, ``5`` Very High).
    impact : GlpiPriority | None, optional
        Impact level (contract enumeration: ``1`` Very Low, ``2`` Low,
        ``3`` Medium, ``4`` High, ``5`` Very High).
    priority : GlpiPriority | None, optional
        Priority override (contract enumeration: ``1`` Very Low, ``2``
        Low, ``3`` Medium, ``4`` High, ``5`` Very High).
    date_creation : datetime | None, optional
        Creation timestamp to set on the ticket record.
    date_mod : datetime | None, optional
        Modification timestamp to set on the ticket record.
    date : datetime | None, optional
        Opening date to assign to the ticket.
    date_solve : datetime | None, optional
        Date to set as the solved timestamp.
    date_close : datetime | None, optional
        Date to set as the closed timestamp.
    type : GlpiTicketType | None, optional
        Ticket category (contract field ``type`` — ``The type of the
        ticket``; enumeration: ``1`` Incident, ``2`` Request).
    external_id : str | None, optional
        Identifier assigned by an external system.
    request_type : IdNameRef | None, optional
        Reference to the request type or channel.
    sla_ttr : IdNameRef | None, optional
        SLA to apply for time-to-resolve.
    sla_tto : IdNameRef | None, optional
        SLA to apply for time-to-own.
    ola_ttr : IdNameRef | None, optional
        OLA to apply for time-to-resolve.
    ola_tto : IdNameRef | None, optional
        OLA to apply for time-to-own.
    sla_level_ttr : IdNameRef | None, optional
        SLA level escalation step for time-to-resolve.
    ola_level_ttr : IdNameRef | None, optional
        OLA level escalation step for time-to-resolve.
    global_validation : GlpiGlobalValidation | None, optional
        Aggregated validation status to set on the ticket (contract
        field ``global_validation`` — ``The global status of the
        validation``; enumeration: ``1`` None, ``2`` Waiting,
        ``3`` Accepted, ``4`` Refused).
    entity : IdNameCompletenameRef | None, optional
        Reference to the GLPI entity that owns the ticket.
    """

    name: str | None = None
    content: GlpiMarkdownContent = None
    is_deleted: bool | None = None
    category: IdNameRef | None = None
    location: IdNameRef | None = None
    urgency: GlpiPriority | None = None
    impact: GlpiPriority | None = None
    priority: GlpiPriority | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    date: datetime | None = None
    date_solve: datetime | None = None
    date_close: datetime | None = None
    type: GlpiTicketType | None = None
    external_id: str | None = None
    request_type: IdNameRef | None = None
    sla_ttr: IdNameRef | None = None
    sla_tto: IdNameRef | None = None
    ola_ttr: IdNameRef | None = None
    ola_tto: IdNameRef | None = None
    sla_level_ttr: IdNameRef | None = None
    ola_level_ttr: IdNameRef | None = None
    global_validation: GlpiGlobalValidation | None = None
    entity: IdNameCompletenameRef | None = None


class PatchTicket(PostTicket):
    """Request body for ``PATCH /Assistance/Ticket/{id}``.

    Every :class:`PostTicket` field applies here too. ``status`` is the
    one field this model adds, and the reason the two are no longer
    interchangeable: GLPI honours a status write on ``PATCH`` and drops
    it on ``POST``.

    The contract disagrees, and it is worth knowing why the package used
    to as well. GLPI publishes ``Ticket.status.id`` as ``readOnly: true``,
    so the field was excluded on the stated grounds that the lifecycle
    could only be moved through the timeline routes. Measured against a
    live GLPI 11 instance, ``PATCH`` with ``{"status": 5}`` returns 200
    and the ticket really does move -- the published contract is simply
    wrong here, the same way it omits the ``Major`` level from
    ``priority`` (see :class:`~glpi_python_client.GlpiPriority`).

    ``status`` is typed as the enum rather than a bare ``int`` because
    **GLPI validates nothing on this field and its interface hides the
    damage**. Writing ``99`` answers 200 and stores it: the API then
    reports ``{"id": 99, "name": "99"}``, the web form displays the
    ticket as *New*, and the ticket disappears from the ticket list
    while staying open in the database. Only the history records what
    happened. A typo such as ``55`` for ``5`` therefore loses a ticket
    silently, and this enum is the only thing on the path that can catch
    it.

    Parameters
    ----------
    status : GlpiTicketStatus | None, optional
        Lifecycle status to move the ticket to (``1`` New, ``2``
        Assigned, ``3`` Planned, ``4`` Pending, ``5`` Solved, ``6``
        Closed, ``10`` Validation). Serialises to the bare integer form,
        which is the spelling measured as honoured; the nested
        ``{"id": ...}`` form works too, but ``status_id`` does not.
    """

    status: GlpiTicketStatus | None = None


class DeleteTicket(GlpiModel):
    """Query parameters for ``DELETE /Assistance/Ticket/{id}``.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the ticket instead of moving
        the record to the GLPI trash. When ``False`` or :data:`None`,
        the server applies its default soft-delete behaviour and the
        ticket can still be restored.
    """

    force: bool | None = None


__all__ = ["DeleteTicket", "GetTicket", "PatchTicket", "PostTicket"]
