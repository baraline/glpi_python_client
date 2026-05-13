"""Synchronous document operations for GLPI v2 clients.

This module covers document listing, metadata lookup, binary download, and
deletion for ticket-linked GLPI documents.
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from tenacity import RetryError

from glpi_python_client.clients.v2.common.constants import (
    DOCUMENT_SUFFIX,
    TICKET_ENDPOINT,
    GlpiId,
)
from glpi_python_client.clients.v2.common.errors import remote_error_message
from glpi_python_client.clients.v2.common.request_http import ensure_response_status
from glpi_python_client.clients.v2.common.response_payloads import (
    timeline_payload_items,
)
from glpi_python_client.content.records.core.scalars import _optional_text
from glpi_python_client.content.records.parsers.documents import _glpi_document_record
from glpi_python_client.models import GlpiDocument

from .transport import SyncTransportMixin

logger = logging.getLogger(__name__)


class SyncDocumentMixin(SyncTransportMixin):
    """Synchronous GLPI ticket document helpers.

    These helpers translate document-related GLPI payloads into typed document
    models and keep metadata enrichment behavior consistent across calls.
    """

    def get_document_records(
        self,
        ticket_id: GlpiId,
        *,
        enrich_metadata: bool = True,
    ) -> list[GlpiDocument]:
        """Fetch the documents linked to one ticket.

        When metadata enrichment is enabled, the method performs per-document
        lookups and logs skipped enrichments without failing the whole batch.
        """

        endpoint = f"{TICKET_ENDPOINT}/{ticket_id}/{DOCUMENT_SUFFIX}"
        response = self._get_request(endpoint)
        if response.status_code not in (200, 206):
            logger.warning(
                "Failed to get documents for ticket %s: %s",
                ticket_id,
                response.status_code,
            )
            return []

        records: list[GlpiDocument] = []
        for relation in timeline_payload_items(response.json()):
            document_id = _optional_text(
                relation.get("documents_id")
            ) or _optional_text(relation.get("id"))
            if document_id is None:
                continue
            metadata: dict[str, Any] = {}
            if enrich_metadata:
                try:
                    document_record = self.get_document_record(document_id)
                    metadata = {
                        "id": document_record.document_id,
                        "filename": document_record.filename,
                        "mime": document_record.mime_type,
                    }
                except (RetryError, ValueError, requests.RequestException) as exc:
                    logger.warning(
                        "Skipping GLPI document %s metadata lookup: %s",
                        document_id,
                        remote_error_message(exc),
                    )
            records.append(_glpi_document_record(relation, metadata=metadata))
        return records

    def get_document_record(self, document_id: GlpiId) -> GlpiDocument:
        """Fetch one GLPI document record by identifier.

        The payload must be a mapping and is converted into a typed
        ``GlpiDocument`` instance before being returned.
        """

        response = self._get_request(
            f"Management/Document/{document_id}",
            skip_entity=True,
        )
        if response.status_code not in (200, 206):
            raise ValueError(
                f"Failed to get document {document_id}: "
                f"{response.status_code} {response.text[:200]}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Unexpected GLPI document payload for {document_id}")
        return _glpi_document_record(payload)

    def download_document_content(self, document_id: GlpiId) -> bytes:
        """Download the raw binary payload for one GLPI document.

        This method is intended for file-content retrieval and returns the raw
        response bytes without additional decoding.
        """

        response = self._get_request(
            f"Management/Document/{document_id}/Download",
            skip_entity=True,
        )
        if response.status_code != 200:
            raise ValueError(
                f"Failed to download document {document_id}: "
                f"{response.status_code} {response.text[:200]}"
            )
        return response.content

    def delete_document(self, document_id: GlpiId) -> None:
        """Delete one GLPI document by identifier.

        Successful deletes return ``None`` and are logged so document cleanup
        workflows can be traced in client logs.
        """

        response = self._delete_request(
            f"Management/Document/{document_id}",
            skip_entity=True,
        )
        ensure_response_status(
            response,
            success_statuses=(200, 204),
            failure_message=f"Failed to delete document {document_id}",
        )
        logger.info("GLPI API deleted document %s", document_id)
        return None
