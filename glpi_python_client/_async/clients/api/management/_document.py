"""GLPI ``/Management/Document`` mixin.

The mixin exposes JSON metadata CRUD operations on the document resource and
a multipart upload helper that delegates to the legacy v1 session because
the v2 API does not advertise a binary upload endpoint in the contract.
"""

from __future__ import annotations

import logging

from glpi_python_client._async.clients.commons._constants import (
    DOCUMENT_ENDPOINT,
    GlpiId,
)
from glpi_python_client._async.clients.commons._http import ensure_response_status
from glpi_python_client._async.clients.commons._transport import TransportMixin
from glpi_python_client._errors import GlpiValidationError
from glpi_python_client.models.api_schema.management._document import (
    DeleteDocument,
    GetDocument,
    PatchDocument,
    PostDocument,
)

logger = logging.getLogger(__name__)


class DocumentMixin(TransportMixin):
    """CRUD and upload helpers for ``/Management/Document``."""

    async def search_documents(
        self,
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
    ) -> list[GetDocument]:
        """Search GLPI documents with an optional raw RSQL filter.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL expression forwarded to the ``filter`` query
            parameter (for example ``"name=='*manual*'"``). When empty
            the parameter is omitted and the server returns its default
            paginated listing.
        limit : int, optional
            Maximum number of records to return (defaults to 50).
        start : int, optional
            Zero-based offset for pagination (defaults to 0).

        Returns
        -------
        list[GetDocument]
            Documents matching the filter window.
        """

        params: dict[str, object] = {"limit": limit, "start": start}
        if rsql_filter:
            params["filter"] = rsql_filter
        return await self._resource_list(
            DOCUMENT_ENDPOINT, GetDocument, params=params, skip_entity=True
        )

    async def get_document(self, document_id: GlpiId) -> GetDocument:
        """Fetch one GLPI document by identifier.

        Parameters
        ----------
        document_id : GlpiId
            Numeric identifier of the document to retrieve.

        Returns
        -------
        GetDocument
            Validated document metadata payload.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        return await self._resource_get(
            f"{DOCUMENT_ENDPOINT}/{document_id}",
            GetDocument,
            failure_message=f"Failed to get document {document_id}",
            skip_entity=True,
        )

    async def create_document(self, document: PostDocument) -> int:
        """Create one GLPI document metadata record.

        Binary uploads use :meth:`upload_document` instead of the JSON
        metadata endpoint exposed here.

        Parameters
        ----------
        document : PostDocument
            Request body describing the document metadata.

        Returns
        -------
        int
            Identifier assigned by the GLPI server to the new document.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        GlpiProtocolError
            If the create response is missing the ``id`` field.
        """

        return await self._resource_create(
            DOCUMENT_ENDPOINT,
            document,
            failure_message="Failed to create document",
            missing_message="GLPI document create response did not include an ID",
            log_message_factory=lambda new_id: f"GLPI API created document {new_id}",
            skip_entity=True,
        )

    async def update_document(
        self, document_id: GlpiId, document: PatchDocument
    ) -> None:
        """Update one GLPI document with a partial body.

        Parameters
        ----------
        document_id : GlpiId
            Numeric identifier of the document to update.
        document : PatchDocument
            Partial request body.

        Returns
        -------
        None

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        await self._resource_update(
            f"{DOCUMENT_ENDPOINT}/{document_id}",
            document,
            failure_message=f"Failed to update document {document_id}",
            log_message=f"GLPI API updated document {document_id}",
        )

    async def delete_document(
        self, document_id: GlpiId, *, force: bool | None = None
    ) -> None:
        """Delete one GLPI document by identifier.

        Parameters
        ----------
        document_id : GlpiId
            Numeric identifier of the document to delete.
        force : bool | None, optional
            When ``True`` the document is permanently deleted instead of
            being moved to the trash.

        Returns
        -------
        None

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        await self._resource_delete(
            f"{DOCUMENT_ENDPOINT}/{document_id}",
            failure_message=f"Failed to delete document {document_id}",
            log_message=f"GLPI API deleted document {document_id}",
            force=force,
            delete_model_cls=DeleteDocument,
            skip_entity=True,
        )

    async def download_document_content(self, document_id: GlpiId) -> bytes:
        """Download the raw binary payload for one GLPI document.

        Parameters
        ----------
        document_id : GlpiId
            Numeric identifier of the document whose binary content is
            requested.

        Returns
        -------
        bytes
            Raw bytes returned by the GLPI download endpoint.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        response = await self._get_request(
            f"{DOCUMENT_ENDPOINT}/{document_id}/Download",
            skip_entity=True,
        )
        ensure_response_status(
            response,
            success_statuses=(200,),
            failure_message=f"Failed to download document {document_id}",
        )
        return response.content

    async def upload_document(
        self,
        *,
        filename: str,
        content: bytes,
        mime_type: str = "application/octet-stream",
        document_name: str | None = None,
        ticket_id: int | None = None,
        entity_id: int | None = None,
    ) -> dict[str, object]:
        """Upload one binary document via the legacy v1 multipart endpoint.

        Document uploads use the legacy v1 multipart endpoint because
        the GLPI v2 API does not advertise a binary upload route. The
        async :class:`~glpi_python_client._async.clients.AsyncGlpiClient`
        offloads this blocking call to a worker thread automatically;
        callers using the sync :class:`~glpi_python_client._async.clients.GlpiClient`
        invoke it directly.

        Parameters
        ----------
        filename : str
            Name to advertise in the multipart form. Required and must
            be non-empty.
        content : bytes
            Raw binary payload to upload.
        mime_type : str, optional
            MIME type advertised in the multipart part (defaults to
            ``application/octet-stream``).
        document_name : str | None, optional
            Human-readable display name. Defaults to ``filename`` when
            omitted.
        ticket_id : int | None, optional
            Identifier of one ticket to attach the uploaded document to.
        entity_id : int | None, optional
            Identifier of one GLPI entity to scope the upload to.

        Returns
        -------
        dict[str, object]
            Raw JSON dictionary returned by the legacy v1 upload
            endpoint.

        Raises
        ------
        GlpiValidationError
            If ``filename`` is empty.
        RuntimeError
            If the v1 session is not configured on the client.
        """

        if not filename:
            raise GlpiValidationError("GLPI document upload requires a filename")
        v1 = self._require_v1_session("document uploads")
        return await v1.upload_document(
            filename,
            content,
            mime_type,
            document_name=document_name,
            ticket_id=ticket_id,
            entity_id=entity_id,
        )


__all__ = ["DocumentMixin"]
