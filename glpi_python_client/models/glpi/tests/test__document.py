from __future__ import annotations

from glpi_python_client import GlpiDocument


def test_document_upload_payload_defaults_mime_type() -> None:
    document = GlpiDocument(ticket_id=123, filename="trace.txt", content=b"trace")

    payload = document.to_api_payload()

    assert payload["mime_type"] == "application/octet-stream"
    assert payload["content"] == b"trace"
