"""Synchronous ticket operations for GLPI v2 clients.

This module contains the ticket search, fetch, create, update, and delete
helpers used by the synchronous high-level client.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any, cast, overload

from glpi_python_client.clients.v2.common.constants import TICKET_ENDPOINT, GlpiId
from glpi_python_client.clients.v2.common.request_http import (
    ensure_response_status,
    require_non_empty_text,
    require_response_text,
)
from glpi_python_client.clients.v2.common.ticket_search import (
    advance_ticket_search_pagination,
    build_ticket_search_params,
    filter_ticket_search_batch,
    is_deleted_ticket,
    merge_list_ticket_fields,
)
from glpi_python_client.content.records.core.normalization import (
    _normalize_ticket_record,
)
from glpi_python_client.content.records.parsers.tickets import (
    _glpi_ticket_record,
)
from glpi_python_client.models import GlpiTicket

from .transport import SyncTransportMixin

logger = logging.getLogger(__name__)


class SyncTicketMixin(SyncTransportMixin):
    """Synchronous GLPI ticket search and mutation helpers.

    The mixin exposes the typed ticket operations while delegating shared field
    and pagination rules to the common helper modules.
    """

    @overload
    def search_ticket_records(
        self,
        query: str | None = None,
        *,
        fields: tuple[str, ...] = (),
        sort: str | None = None,
        batch_size: None = None,
        include_deleted_ticket: bool = False,
    ) -> list[GlpiTicket]: ...

    @overload
    def search_ticket_records(
        self,
        query: str | None = None,
        *,
        fields: tuple[str, ...] = (),
        sort: str | None = None,
        batch_size: int,
        include_deleted_ticket: bool = False,
    ) -> Iterator[list[GlpiTicket]]: ...

    def search_ticket_records(
        self,
        query: str | None = None,
        *,
        fields: tuple[str, ...] = (),
        sort: str | None = None,
        batch_size: int | None = None,
        include_deleted_ticket: bool = False,
    ) -> list[GlpiTicket] | Iterator[list[GlpiTicket]]:
        """Search GLPI tickets and return either a full list or record batches.

        Passing ``batch_size`` switches the method into streaming mode and
        returns an iterator of typed ticket batches instead of materializing the
        full result set.
        """

        if batch_size is not None and batch_size < 1:
            raise ValueError("batch_size must be a positive integer or None")

        merged_fields = merge_list_ticket_fields(list(fields) or None)
        batches = self._iter_ticket_record_batches(
            query=query,
            fields=merged_fields,
            sort=sort,
            batch_size=batch_size,
            include_deleted_ticket=include_deleted_ticket,
        )
        if batch_size is not None:
            return batches

        records: list[GlpiTicket] = []
        for page in batches:
            records.extend(page)
        return records

    def _iter_ticket_record_batches(
        self,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        sort: str | None = None,
        batch_size: int | None = None,
        include_deleted_ticket: bool = False,
    ) -> Iterator[list[GlpiTicket]]:
        """Yield typed ticket batches produced from paginated raw payloads.

        This helper sits between raw payload pagination and public return types,
        ensuring each yielded batch already contains parsed ``GlpiTicket``
        objects.
        """

        for page in self._yield_ticket_payloads(
            query=query,
            fields=fields,
            sort=sort,
            batch_size=batch_size,
            include_deleted_ticket=include_deleted_ticket,
        ):
            yield [
                _glpi_ticket_record(raw_ticket)
                for raw_ticket in page
                if isinstance(raw_ticket, dict)
            ]

    def get_ticket_record(
        self,
        ticket_id: GlpiId,
        *,
        include_deleted_ticket: bool = False,
    ) -> GlpiTicket:
        """Fetch one GLPI ticket by identifier.

        Deleted tickets are rejected by default so single-record fetch behavior
        stays aligned with the default search behavior.
        """

        response = self._get_request(f"{TICKET_ENDPOINT}/{ticket_id}")
        if response.status_code not in (200, 206):
            raise ValueError(
                f"Failed to get ticket {ticket_id}: {response.status_code}"
            )
        payload = _normalize_ticket_record(response.json())
        if not isinstance(payload, dict):
            raise ValueError(f"Unexpected GLPI ticket payload for {ticket_id}")
        if not include_deleted_ticket and is_deleted_ticket(payload):
            raise ValueError(
                f"Ticket {ticket_id} is deleted and excluded from fetch results"
            )
        return _glpi_ticket_record(payload)

    def create_ticket(self, ticket: GlpiTicket) -> str:
        """Create a GLPI ticket and return the identifier assigned by GLPI.

        The ticket name precondition is enforced locally before the request is
        sent, and the response must contain a created ticket ID.
        """

        require_non_empty_text(
            ticket.name,
            error_message="GLPI ticket creation requires a name",
        )

        payload_data = ticket.to_api_payload(
            entity_id=self.glpi_entity,
            include_entity=True,
        )
        response = self._post_request(TICKET_ENDPOINT, payload_data)
        ensure_response_status(
            response,
            success_statuses=(200, 201),
            failure_message="Failed to create ticket",
        )
        ticket_id = require_response_text(
            response,
            keys=("id",),
            missing_message="GLPI create response did not include a ticket ID",
        )
        logger.info(
            "GLPI API created ticket %s fields=%s",
            ticket_id,
            sorted(payload_data),
        )
        return ticket_id

    def update_ticket(
        self,
        ticket_id: GlpiId,
        ticket: GlpiTicket,
        *,
        field_mask: tuple[str, ...] = (),
    ) -> None:
        """Update one GLPI ticket with the provided field changes.

        Optional field masks are forwarded to the model serializer so callers
        can restrict the update payload to a specific subset of fields.
        """

        payload_data = ticket.to_api_payload(
            entity_id=self.glpi_entity,
            include_entity=False,
            field_mask=field_mask,
        )
        response = self._update_request(
            f"{TICKET_ENDPOINT}/{ticket_id}",
            payload_data,
        )
        ensure_response_status(
            response,
            success_statuses=(200, 204),
            failure_message=f"Failed to update ticket {ticket_id}",
        )
        logger.info(
            "GLPI API updated ticket %s fields=%s",
            ticket_id,
            sorted(payload_data),
        )
        return None

    def delete_ticket(self, ticket_id: GlpiId) -> None:
        """Delete one GLPI ticket by identifier.

        The method logs successful deletion and returns ``None`` to match the
        package's mutation-helper conventions.
        """

        response = self._delete_request(f"{TICKET_ENDPOINT}/{ticket_id}")
        ensure_response_status(
            response,
            success_statuses=(200, 204),
            failure_message=f"Failed to delete ticket {ticket_id}",
        )
        logger.info("GLPI API deleted ticket %s", ticket_id)
        return None

    def _yield_ticket_payloads(
        self,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        sort: str | None = None,
        batch_size: int | None = None,
        include_deleted_ticket: bool = False,
    ) -> Iterator[list[dict[str, Any]]]:
        """Yield paginated raw ticket payload batches from the GLPI API.

        Pagination continues until the server indicates no more content or the
        observed page-size heuristic shows that iteration is complete.
        """

        params = build_ticket_search_params(
            query=query,
            fields=fields,
            sort=sort,
            batch_size=batch_size,
        )

        observed_page_size = batch_size
        while True:
            current_start = cast(int, params["start"])
            response = self._get_request(TICKET_ENDPOINT, params)
            if response.status_code not in (200, 206):
                logger.info(
                    "GLPI ticket search returned status %s (start=%d)",
                    response.status_code,
                    current_start,
                )
                return

            batch = response.json()
            if not isinstance(batch, list) or not batch:
                logger.info(
                    "GLPI ticket search returned empty batch (start=%d)",
                    current_start,
                )
                return

            logger.info(
                "GLPI ticket search: batch of %d tickets (start=%d)",
                len(batch),
                current_start,
            )
            result_batch, deleted_count = filter_ticket_search_batch(
                batch,
                include_deleted_ticket=include_deleted_ticket,
            )
            if deleted_count:
                logger.info(
                    "GLPI ticket search: excluded %d deleted tickets (start=%d)",
                    deleted_count,
                    current_start,
                )
            if result_batch:
                yield result_batch

            next_start, observed_page_size, should_continue = (
                advance_ticket_search_pagination(
                    current_start=current_start,
                    page_size=len(batch),
                    content_range=response.headers.get("Content-Range", ""),
                    observed_page_size=observed_page_size,
                )
            )
            params["start"] = next_start
            if not should_continue:
                return
