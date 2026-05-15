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
    GlpiTicketType,
)


class _TicketTeamMember(GlpiModel):
    """One inline team-member entry of the ``Ticket.team`` array.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI member identifier.
    name : str | None, optional
        Member display name.
    type : str | None, optional
        GLPI member type, such as ``"User"`` or ``"Group"``.
    role : str | None, optional
        GLPI ticket role assigned to the member.
    """

    id: int | None = None
    name: str | None = None
    type: str | None = None
    role: str | None = None


class GetTicket(GlpiModel):
    """Response shape returned by ``GET /Assistance/Ticket`` endpoints.

    Mirrors ``components.schemas.Ticket``.
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

    Read-only contract fields are excluded. ``status`` is read-only on the
    contract because GLPI manages ticket lifecycle through dedicated routes
    (followups, solutions, validation), so it is omitted from write models.
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
    """Request body for ``PATCH /Assistance/Ticket/{id}``."""


class DeleteTicket(GlpiModel):
    """Query parameters for ``DELETE /Assistance/Ticket/{id}``.

    Parameters
    ----------
    force : bool | None, optional
        Permanently delete the ticket instead of moving it to the trash.
    """

    force: bool | None = None


__all__ = ["DeleteTicket", "GetTicket", "PatchTicket", "PostTicket"]
