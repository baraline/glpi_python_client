"""GLPI document record parsing helpers.

This module converts raw document payloads and optional metadata overlays into
the package's typed ``GlpiDocument`` model.
"""

from __future__ import annotations

from typing import Any

from glpi_python_client.content.records.core.scalars import _optional_text
from glpi_python_client.models import GlpiDocument


def _glpi_document_record(
    raw_document: dict[str, Any],
    *,
    metadata: dict[str, Any] | None = None,
) -> GlpiDocument:
    """Build a ``GlpiDocument`` from one raw document payload.

    The parser can merge additional metadata gathered from a separate document
    lookup before normalizing identifiers, filenames, and MIME types.
    """

    merged = dict(raw_document)
    if metadata:
        merged.update({f"metadata_{key}": value for key, value in metadata.items()})
    document_id = (
        _optional_text(merged.get("documents_id"))
        or _optional_text(merged.get("metadata_id"))
        or _optional_text(merged.get("id"))
    )
    filename = (
        _optional_text(merged.get("filename"))
        or _optional_text(merged.get("name"))
        or _optional_text(merged.get("metadata_filename"))
        or _optional_text(merged.get("metadata_name"))
        or document_id
    )
    if document_id is None or filename is None:
        raise ValueError("GLPI document payload did not include an ID and filename")
    return GlpiDocument(
        document_id=document_id,
        filename=filename,
        mime_type=_optional_text(merged.get("mime"))
        or _optional_text(merged.get("metadata_mime")),
        linked_document_id=_optional_text(merged.get("documents_id")),
    )
