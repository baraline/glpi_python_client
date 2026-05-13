"""Typed GLPI solution model.

The solution model stores normalized Markdown content together with the metadata
returned by GLPI solution timeline endpoints.
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


class GlpiSolution(ApiPayloadMixin, GlpiModel):
    """GLPI solution rich object.

    Parameters
    ----------
    content : str | None, optional
        Solution body in canonical Markdown.
    solution_id : str | None, optional
        Native GLPI solution identifier.
    created_at : datetime | None, optional
        Creation timestamp.
    updated_at : datetime | None, optional
        Last update timestamp.
    author : GlpiUser | None, optional
        Solution author.
    attachment_document_ids : tuple[str, ...], optional
        GLPI document identifiers referenced by the solution.
    """

    solution_id: str | None = None
    content: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    author: GlpiUser | None = None
    attachment_document_ids: tuple[str, ...] = ()

    def _build_api_payload(self) -> dict[str, object]:
        """Return the raw GLPI API request body for the solution.

        Returns
        -------
        dict[str, object]
            Raw solution API request body.
        """

        return drop_empty_payload_values(
            {"content": GlpiContentConverter.to_transport(self.content)}
        )
