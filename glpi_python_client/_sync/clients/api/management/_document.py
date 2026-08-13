"""GLPI ``/Management/Document`` mixin.

The mixin exposes JSON metadata CRUD operations on the document resource and
a multipart upload helper that delegates to the legacy v1 session because
the v2 API does not advertise a binary upload endpoint in the contract.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

from glpi_python_client._sync.clients.commons._constants import (
    DOCUMENT_ENDPOINT,
    GlpiId,
)
from glpi_python_client._sync.clients.commons._http import ensure_response_status
from glpi_python_client._sync.clients.commons._transport import TransportMixin
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

    def search_documents(
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
        return self._resource_list(
            DOCUMENT_ENDPOINT, GetDocument, params=params, skip_entity=True
        )

    def iter_search_documents(
        self,
        rsql_filter: str = "",
        *,
        batch_size: int = 50,
    ) -> Iterator[list[GetDocument]]:
        """Yield successive pages of GLPI documents until exhausted.

        The generator drives pagination automatically by advancing the
        ``start`` offset after each batch. Iteration stops when the server
        returns fewer items than ``batch_size``, which signals the last page.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
            Empty by default, which lists every visible record.
        batch_size : int, optional
            Number of records requested per page (default 50). Acts as the
            ``limit`` parameter on each underlying :meth:`search_documents`
            call.

        Yields
        ------
        list[GetDocument]
            One page per iteration. The last yielded batch may be shorter
            than ``batch_size``.
        """

        start = 0
        while True:
            batch = self.search_documents(
                rsql_filter,
                limit=batch_size,
                start=start,
            )
            if batch:
                yield batch
            if len(batch) < batch_size:
                break
            start += batch_size

    def get_document(self, document_id: GlpiId) -> GetDocument:
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

        return self._resource_get(
            f"{DOCUMENT_ENDPOINT}/{document_id}",
            GetDocument,
            failure_message=f"Failed to get document {document_id}",
            skip_entity=True,
        )

    def create_document(self, document: PostDocument) -> int:
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

        return self._resource_create(
            DOCUMENT_ENDPOINT,
            document,
            failure_message="Failed to create document",
            missing_message="GLPI document create response did not include an ID",
            log_message_factory=lambda new_id: f"GLPI API created document {new_id}",
            skip_entity=True,
        )

    def update_document(
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

        self._resource_update(
            f"{DOCUMENT_ENDPOINT}/{document_id}",
            document,
            failure_message=f"Failed to update document {document_id}",
            log_message=f"GLPI API updated document {document_id}",
        )

    def delete_document(
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

        self._resource_delete(
            f"{DOCUMENT_ENDPOINT}/{document_id}",
            failure_message=f"Failed to delete document {document_id}",
            log_message=f"GLPI API deleted document {document_id}",
            force=force,
            delete_model_cls=DeleteDocument,
            skip_entity=True,
        )

    def download_document_content(self, document_id: GlpiId) -> bytes:
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

        response = self._get_request(
            f"{DOCUMENT_ENDPOINT}/{document_id}/Download",
            skip_entity=True,
        )
        ensure_response_status(
            response,
            success_statuses=(200,),
            failure_message=f"Failed to download document {document_id}",
        )
        return response.content

    def stream_document_content(
        self,
        document_id: GlpiId,
        *,
        chunk_size: int = 65536,
    ) -> Iterator[bytes]:
        """Stream the binary payload of one GLPI document in chunks.

        Use this instead of :meth:`download_document_content` when the file
        may be large: that method holds the whole body in memory before
        returning, so a 500 MB attachment costs 500 MB of process memory
        even if the caller only writes it straight to disk.

        Parameters
        ----------
        document_id : GlpiId
            Numeric identifier of the document whose binary content is
            requested.
        chunk_size : int, optional
            Bytes requested per chunk (defaults to 64 KiB).

        Yields
        ------
        bytes
            Successive chunks of the document body. The final chunk may be
            shorter than ``chunk_size``.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.

        Examples
        --------
        Writing a document to disk without buffering it::

            with open("attachment.pdf", "wb") as handle:
                async for chunk in client.stream_document_content(42):
                    handle.write(chunk)
        """

        for chunk in self._stream_request(
            f"{DOCUMENT_ENDPOINT}/{document_id}/Download",
            chunk_size=chunk_size,
            skip_entity=True,
            failure_message=f"Failed to download document {document_id}",
        ):
            yield chunk

    def upload_document(
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
        upload is dispatched through the same v1 session as every other
        v1 call, so it needs ``v1_base_url`` and ``v1_user_token`` to be
        configured on the client.

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
        return v1.upload_document(
            filename,
            content,
            mime_type,
            document_name=document_name,
            ticket_id=ticket_id,
            entity_id=entity_id,
        )


__all__ = ["DocumentMixin"]
