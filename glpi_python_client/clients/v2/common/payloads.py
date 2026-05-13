"""Request payload builders for GLPI v2 client operations.

These helpers keep small but repeated mutation payload rules out of the public
client methods so sync and async implementations can share them directly.
"""

from __future__ import annotations

from .constants import GlpiId


def build_team_member_payload(
    *,
    member_type: str,
    member_id: int,
    role: str,
) -> dict[str, object]:
    """Build the API payload used to add or remove one team member.

    The returned mapping matches the shape expected by the GLPI team-member
    endpoint for both creation and removal workflows.
    """

    return {
        "type": member_type,
        "id": member_id,
        "role": role,
    }


def prepare_document_upload(
    *,
    ticket_id: GlpiId | None,
    filename: str | None,
    content: bytes | None,
    mime_type: str | None,
) -> tuple[int, str, bytes, str, str]:
    """Validate a document upload request and return normalized upload data.

    This helper enforces the package-level upload prerequisites and converts the
    mixed model fields into the concrete values required by the legacy v1 upload
    API.
    """

    if ticket_id is None:
        raise ValueError("GLPI document upload requires a ticket_id")
    if filename is None:
        raise ValueError("GLPI document upload requires a filename")
    if content is None:
        raise ValueError("GLPI document upload requires file content")

    parsed_ticket_id = int(ticket_id)
    document_name = f"Document ticket {parsed_ticket_id}"
    effective_mime_type = (
        mime_type if mime_type is not None else "application/octet-stream"
    )
    return parsed_ticket_id, filename, content, effective_mime_type, document_name
