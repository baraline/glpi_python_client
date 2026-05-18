"""Synchronous GLPI ``/Assistance/Ticket/{id}/TeamMember`` mixin.

The team-member endpoint exposes list, add, and remove operations on a
ticket. The mixin uses the ``api_schema`` ``TeamMember`` models and lets
the GLPI API perform server-side validation of role and itemtype values.
"""

from __future__ import annotations

import logging

from glpi_python_client.clients.commons._constants import (
    TEAM_MEMBER_SUFFIX,
    TICKET_ENDPOINT,
    GlpiId,
)
from glpi_python_client.clients.commons._http import ensure_response_status
from glpi_python_client.clients.commons._payloads import model_to_payload
from glpi_python_client.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema.assistance._team import (
    GetTeamMember,
    PostTeamMember,
)

logger = logging.getLogger(__name__)


class TeamMemberMixin(TransportMixin):
    """Synchronous helpers for the ticket team-member endpoint."""

    def list_ticket_team_members(self, ticket_id: GlpiId) -> list[GetTeamMember]:
        """List the team members currently linked to one ticket.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the ticket whose team members are listed.

        Returns
        -------
        list[GetTeamMember]
            Team members validated against the contract ``TeamMember`` schema.

        Raises
        ------
        ValueError
            If the GLPI server returns a non-success HTTP status.
        """

        return self._resource_list(
            f"{TICKET_ENDPOINT}/{ticket_id}/{TEAM_MEMBER_SUFFIX}",
            GetTeamMember,
            failure_message=f"Failed to list ticket team members for {ticket_id}",
        )

    def add_ticket_team_member(self, ticket_id: GlpiId, member: PostTeamMember) -> None:
        """Add one team member to a ticket.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the ticket to receive the new member.
        member : PostTeamMember
            Request body describing the member. The ``id`` field is the
            target user/group/supplier identifier, ``type`` is one of
            ``"User"``, ``"Group"`` or ``"Supplier"``, and ``role`` is one
            of ``"requester"``, ``"assigned"`` or ``"observer"``.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the GLPI server returns a non-success HTTP status.
        """

        endpoint = f"{TICKET_ENDPOINT}/{ticket_id}/{TEAM_MEMBER_SUFFIX}"
        response = self._post_request(endpoint, model_to_payload(member))
        ensure_response_status(
            response,
            success_statuses=(200, 201),
            failure_message=f"Failed to add team member on ticket {ticket_id}",
        )
        logger.info("GLPI API added team member on ticket %s", ticket_id)

    def remove_ticket_team_member(
        self, ticket_id: GlpiId, member: PostTeamMember
    ) -> None:
        """Remove one team member from a ticket.

        Parameters
        ----------
        ticket_id : GlpiId
            Numeric identifier of the ticket the member belongs to.
        member : PostTeamMember
            Request body identifying the member to remove (same shape as
            :meth:`add_ticket_team_member`).

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the GLPI server returns a non-success HTTP status.
        """

        self._resource_delete(
            f"{TICKET_ENDPOINT}/{ticket_id}/{TEAM_MEMBER_SUFFIX}",
            failure_message=f"Failed to remove team member on ticket {ticket_id}",
            log_message=f"GLPI API removed team member on ticket {ticket_id}",
            body=model_to_payload(member),
        )


__all__ = ["TeamMemberMixin"]
