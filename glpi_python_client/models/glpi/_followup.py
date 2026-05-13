"""Typed GLPI followup model.

The followup model stores normalized Markdown content and the metadata returned
by GLPI timeline endpoints.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.content.conversion import GlpiContentConverter
from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models._payload import (
    ApiPayloadMixin,
    drop_empty_payload_values,
)
from glpi_python_client.models.glpi._user import GlpiUser


class GlpiFollowup(ApiPayloadMixin, GlpiModel):
    """GLPI followup rich object.

    Parameters
    ----------
    content : str | None, optional
        Followup body in canonical Markdown.
    followup_id : str | None, optional
        Native GLPI followup identifier.
    created_at : datetime | None, optional
        Creation timestamp.
    updated_at : datetime | None, optional
        Last update timestamp.
    author : GlpiUser | None, optional
        Followup author.
    editor : GlpiUser | None, optional
        Last editor.
    is_private : bool, optional
        Whether the followup is private.
    attachment_document_ids : tuple[str, ...], optional
        GLPI document identifiers referenced by the followup.
    """

    followup_id: str | None = None
    content: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    author: GlpiUser | None = None
    editor: GlpiUser | None = None
    is_private: bool = False
    attachment_document_ids: tuple[str, ...] = ()

    def _build_api_payload(self) -> dict[str, object]:
        """Return the raw GLPI API request body for the followup.

        Returns
        -------
        dict[str, object]
            Raw followup API request body.
        """

        payload: dict[str, object] = {
            "content": GlpiContentConverter.to_transport(self.content),
            "is_private": self.is_private,
        }
        author_id = getattr(self.author, "user_id", None)
        if author_id is not None:
            payload["user"] = {"id": author_id}
        editor_id = getattr(self.editor, "user_id", None)
        if editor_id is not None:
            payload["user_editor"] = {"id": editor_id}
        if self.created_at is not None:
            timestamp = self.created_at.strftime("%Y-%m-%d %H:%M:%S")
            payload["date_creation"] = timestamp
            payload["date"] = timestamp
        if self.updated_at is not None:
            payload["date_mod"] = self.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        return drop_empty_payload_values(payload)
