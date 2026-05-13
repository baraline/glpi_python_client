"""Typed GLPI document model.

The document model represents both fetched document metadata and the input data
needed by the legacy upload workflow.
"""

from __future__ import annotations

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models._payload import ApiPayloadMixin


class GlpiDocument(ApiPayloadMixin, GlpiModel):
    """GLPI document rich object.

    Parameters
    ----------
    document_id : str | None, optional
        Native GLPI document identifier.
    filename : str | None, optional
        Document filename.
    mime_type : str | None, optional
        MIME type.
    linked_document_id : str | None, optional
        Linked GLPI document identifier when different from ``document_id``.
    ticket_id : int | None, optional
        Owning ticket ID for uploads.
    content : bytes | None, optional
        Binary payload used for uploads.
    document_name : str | None, optional
        GLPI document title used during upload.
    """

    document_id: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    linked_document_id: str | None = None
    ticket_id: int | str | None = None
    content: bytes | None = None
    document_name: str | None = None

    def _build_api_payload(self) -> dict[str, object]:
        """Return the raw upload payload consumed by the GLPI document gateway.

        Returns
        -------
        dict[str, object]
            Raw upload payload.
        """

        return {
            "ticket_id": self.ticket_id,
            "filename": self.filename,
            "content": self.content,
            "mime_type": self.mime_type
            if self.mime_type is not None
            else "application/octet-stream",
            "document_name": self.document_name,
        }
