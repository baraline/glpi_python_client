"""Asynchronous timeline operations for GLPI v2 clients.

This module groups async followup, task, solution, and attachment-lookup
helpers for ticket timeline data.
"""

from __future__ import annotations

import asyncio
import logging

from tenacity import RetryError

from glpi_python_client.clients.v2.common.constants import (
    FOLLOWUP_SUFFIX,
    SOLUTION_SUFFIX,
    TASK_SUFFIX,
    TICKET_ENDPOINT,
    GlpiId,
)
from glpi_python_client.clients.v2.common.errors import remote_error_message
from glpi_python_client.clients.v2.common.request_http import (
    ensure_response_status,
    require_response_text,
)
from glpi_python_client.clients.v2.common.response_payloads import (
    timeline_records_from_response,
)
from glpi_python_client.content.records.core.scalars import _optional_text
from glpi_python_client.content.records.parsers.timeline import (
    _glpi_followup_record,
    _glpi_solution_record,
    _glpi_task_record,
)
from glpi_python_client.models import GlpiFollowup, GlpiSolution, GlpiTask

from .transport import AsyncTransportMixin

logger = logging.getLogger(__name__)


class AsyncTimelineMixin(AsyncTransportMixin):
    """Asynchronous followup, task, and solution helpers.

    The mixin keeps ticket timeline behavior together because these endpoints
    share parsing, logging, and optional legacy attachment lookup rules.
    """

    async def get_followup_records(self, ticket_id: GlpiId) -> list[GlpiFollowup]:
        """Fetch the followups associated with one ticket.

        Non-success responses are logged and normalized to an empty list so the
        helper behaves like the other async timeline list operations.
        """

        endpoint = f"{TICKET_ENDPOINT}/{ticket_id}/{FOLLOWUP_SUFFIX}"
        response = await self._get_request(endpoint)
        if response.status_code not in (200, 206):
            logger.warning(
                "Failed to get followups for ticket %s: %s",
                ticket_id,
                response.status_code,
            )
            return []
        return timeline_records_from_response(
            response,
            record_factory=_glpi_followup_record,
        )

    async def get_task_records(self, ticket_id: GlpiId) -> list[GlpiTask]:
        """Fetch the tasks associated with one ticket.

        Returned records are parsed into typed ``GlpiTask`` instances using the
        shared timeline response handling helpers.
        """

        endpoint = f"{TICKET_ENDPOINT}/{ticket_id}/{TASK_SUFFIX}"
        response = await self._get_request(endpoint)
        if response.status_code not in (200, 206):
            logger.warning(
                "Failed to get tasks for ticket %s: %s",
                ticket_id,
                response.status_code,
            )
            return []
        return timeline_records_from_response(
            response,
            record_factory=_glpi_task_record,
        )

    async def get_followup_attachment_document_ids(
        self, followup_id: GlpiId
    ) -> tuple[str, ...]:
        """Fetch document IDs linked directly to one followup through v1.

        Attachment lookup is best-effort because it depends on the optional
        legacy v1 session and runs through ``asyncio.to_thread`` at that narrow
        blocking boundary.
        """

        v1_session = self._v1
        if v1_session is None:
            return ()

        document_ids: list[str] = []
        seen_document_ids: set[str] = set()
        try:
            relations = await asyncio.to_thread(
                v1_session.get_sub_items,
                "ITILFollowup",
                followup_id,
                "Document_Item",
            )
        except (RetryError, ValueError) as exc:
            logger.warning(
                "Skipping GLPI followup %s attachment lookup after v1 API failure: %s",
                followup_id,
                remote_error_message(exc),
            )
            return ()
        for relation in relations:
            document_id = _optional_text(relation.get("documents_id"))
            if document_id is None or document_id in seen_document_ids:
                continue
            seen_document_ids.add(document_id)
            document_ids.append(document_id)
        return tuple(document_ids)

    async def get_solution_attachment_document_ids(
        self, solution_id: GlpiId
    ) -> tuple[str, ...]:
        """Fetch document IDs linked directly to one solution through v1.

        This mirrors followup attachment lookup and preserves first-seen order
        while removing duplicate document identifiers.
        """

        v1_session = self._v1
        if v1_session is None:
            return ()

        document_ids: list[str] = []
        seen_document_ids: set[str] = set()
        try:
            relations = await asyncio.to_thread(
                v1_session.get_sub_items,
                "ITILSolution",
                solution_id,
                "Document_Item",
            )
        except (RetryError, ValueError) as exc:
            logger.warning(
                "Skipping GLPI solution %s attachment lookup after v1 API failure: %s",
                solution_id,
                remote_error_message(exc),
            )
            return ()
        for relation in relations:
            document_id = _optional_text(relation.get("documents_id"))
            if document_id is None or document_id in seen_document_ids:
                continue
            seen_document_ids.add(document_id)
            document_ids.append(document_id)
        return tuple(document_ids)

    async def get_solution_records(self, ticket_id: GlpiId) -> list[GlpiSolution]:
        """Fetch the solutions associated with one ticket.

        Each returned item is parsed into a typed ``GlpiSolution`` record using
        the shared timeline parsing helpers.
        """

        endpoint = f"{TICKET_ENDPOINT}/{ticket_id}/{SOLUTION_SUFFIX}"
        response = await self._get_request(endpoint)
        if response.status_code not in (200, 206):
            logger.warning(
                "Failed to get solutions for ticket %s: %s",
                ticket_id,
                response.status_code,
            )
            return []
        return timeline_records_from_response(
            response,
            record_factory=_glpi_solution_record,
        )

    async def create_followup(
        self,
        ticket_id: GlpiId,
        followup: GlpiFollowup,
    ) -> str:
        """Create a GLPI followup and return the identifier assigned by GLPI.

        The response may expose the created ID under different keys, so the
        helper normalizes that lookup before returning to callers.
        """

        endpoint = f"{TICKET_ENDPOINT}/{ticket_id}/{FOLLOWUP_SUFFIX}"
        payload_data = followup.to_api_payload()
        response = await self._post_request(endpoint, payload_data)
        ensure_response_status(
            response,
            success_statuses=(200, 201),
            failure_message=f"Failed to post followup on ticket {ticket_id}",
        )
        followup_id = require_response_text(
            response,
            keys=("id", "followup_id"),
            missing_message="GLPI followup create response did not include an ID",
        )
        logger.info(
            "GLPI API created %s followup %s on ticket %s",
            "private" if payload_data.get("is_private") else "public",
            followup_id,
            ticket_id,
        )
        return followup_id

    async def update_followup(
        self,
        ticket_id: GlpiId,
        followup_id: GlpiId,
        followup: GlpiFollowup,
    ) -> None:
        """Update one GLPI followup on a ticket.

        The followup model is serialized as-is and the method returns ``None``
        once GLPI accepts the update.
        """

        endpoint = f"{TICKET_ENDPOINT}/{ticket_id}/{FOLLOWUP_SUFFIX}/{followup_id}"
        payload_data = followup.to_api_payload()
        response = await self._update_request(endpoint, payload_data)
        ensure_response_status(
            response,
            success_statuses=(200, 204),
            failure_message=(
                f"Failed to patch followup {followup_id} on ticket {ticket_id}"
            ),
        )
        logger.info(
            "GLPI API updated followup %s on ticket %s fields=%s",
            followup_id,
            ticket_id,
            sorted(payload_data),
        )
        return None

    async def delete_followup(self, ticket_id: GlpiId, followup_id: GlpiId) -> None:
        """Delete one GLPI ticket followup by identifier.

        Successful deletes are logged with both ticket and followup context to
        help trace timeline mutations.
        """

        endpoint = f"{TICKET_ENDPOINT}/{ticket_id}/{FOLLOWUP_SUFFIX}/{followup_id}"
        response = await self._delete_request(endpoint)
        ensure_response_status(
            response,
            success_statuses=(200, 204),
            failure_message=(
                f"Failed to delete followup {followup_id} on ticket {ticket_id}"
            ),
        )
        logger.info("GLPI API deleted followup %s on ticket %s", followup_id, ticket_id)
        return None

    async def create_solution(
        self,
        ticket_id: GlpiId,
        solution: GlpiSolution,
    ) -> str:
        """Create a GLPI solution and return the identifier assigned by GLPI.

        As with followups, the created solution identifier is normalized from
        the response payload before being returned.
        """

        endpoint = f"{TICKET_ENDPOINT}/{ticket_id}/{SOLUTION_SUFFIX}"
        payload_data = solution.to_api_payload()
        response = await self._post_request(endpoint, payload_data)
        ensure_response_status(
            response,
            success_statuses=(200, 201),
            failure_message=f"Failed to post solution on ticket {ticket_id}",
        )
        solution_id = require_response_text(
            response,
            keys=("id", "solution_id"),
            missing_message="GLPI solution create response did not include an ID",
        )
        logger.info("GLPI API created solution %s on ticket %s", solution_id, ticket_id)
        return solution_id

    async def delete_solution(self, ticket_id: GlpiId, solution_id: GlpiId) -> None:
        """Delete one GLPI ticket solution by identifier.

        The helper returns ``None`` after a successful delete response and logs
        the mutation for troubleshooting and auditability.
        """

        endpoint = f"{TICKET_ENDPOINT}/{ticket_id}/{SOLUTION_SUFFIX}/{solution_id}"
        response = await self._delete_request(endpoint)
        ensure_response_status(
            response,
            success_statuses=(200, 204),
            failure_message=(
                f"Failed to delete solution {solution_id} on ticket {ticket_id}"
            ),
        )
        logger.info("GLPI API deleted solution %s on ticket %s", solution_id, ticket_id)
        return None
