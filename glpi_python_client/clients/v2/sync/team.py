"""Synchronous team member operations for GLPI v2 clients.

This module provides the ticket team-member helpers that list, add, and remove
assigned members through the GLPI API.
"""

from __future__ import annotations

import logging

from glpi_python_client.clients.v2.common.constants import (
    TEAM_MEMBER_SUFFIX,
    TICKET_ENDPOINT,
    GlpiId,
)
from glpi_python_client.clients.v2.common.payloads import build_team_member_payload
from glpi_python_client.clients.v2.common.request_http import ensure_response_status
from glpi_python_client.clients.v2.common.response_payloads import list_payload_records
from glpi_python_client.content.records.parsers.team import _glpi_team_member_record
from glpi_python_client.models import GlpiTeamMember

from .transport import SyncTransportMixin

logger = logging.getLogger(__name__)


class SyncTeamMixin(SyncTransportMixin):
    """Synchronous GLPI ticket team member helpers.

    The mixin keeps team-member payload construction and response handling out
    of the public client class.
    """

    def get_team_member_records(self, ticket_id: GlpiId) -> list[GlpiTeamMember]:
        """Fetch the team members currently linked to one ticket.

        Non-success list responses are treated as empty results and logged as a
        warning rather than raising immediately.
        """

        endpoint = f"{TICKET_ENDPOINT}/{ticket_id}/{TEAM_MEMBER_SUFFIX}"
        response = self._get_request(endpoint)
        if response.status_code not in (200, 206):
            logger.warning(
                "Failed to get team members for ticket %s: %s",
                ticket_id,
                response.status_code,
            )
            return []
        return list_payload_records(
            response.json(),
            record_factory=_glpi_team_member_record,
        )

    def add_team_member(
        self,
        ticket_id: GlpiId,
        member: GlpiTeamMember,
    ) -> None:
        """Add one team member to a GLPI ticket.

        The method builds the API payload from the typed member object and logs
        the resulting membership change on success.
        """

        endpoint = f"{TICKET_ENDPOINT}/{ticket_id}/{TEAM_MEMBER_SUFFIX}"
        payload = build_team_member_payload(
            member_type=member.member_type,
            member_id=member.member_id,
            role=member.role,
        )
        response = self._post_request(endpoint, payload)
        ensure_response_status(
            response,
            success_statuses=(200, 201),
            failure_message=(
                "Failed to add team member "
                f"{member.member_type}:{member.member_id} "
                f"role={member.role} on ticket {ticket_id}"
            ),
        )
        logger.info(
            "GLPI API added team member %s:%s role=%s on ticket %s",
            member.member_type,
            member.member_id,
            member.role,
            ticket_id,
        )
        return None

    def remove_team_member(
        self,
        ticket_id: GlpiId,
        member: GlpiTeamMember,
    ) -> None:
        """Remove one team member from a GLPI ticket.

        The payload shape mirrors team-member creation so the same member model
        can be used for both add and remove workflows.
        """

        endpoint = f"{TICKET_ENDPOINT}/{ticket_id}/{TEAM_MEMBER_SUFFIX}"
        payload = build_team_member_payload(
            member_type=member.member_type,
            member_id=member.member_id,
            role=member.role,
        )
        response = self._delete_request(endpoint, payload)
        ensure_response_status(
            response,
            success_statuses=(200, 204),
            failure_message=(
                "Failed to remove team member "
                f"{member.member_type}:{member.member_id} "
                f"role={member.role} from ticket {ticket_id}"
            ),
        )
        logger.info(
            "GLPI API removed team member %s:%s role=%s from ticket %s",
            member.member_type,
            member.member_id,
            member.role,
            ticket_id,
        )
        return None
