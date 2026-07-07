"""GLPI ``KBArticleRevision`` schema for the KB revision endpoints.

The endpoints live under
``/Knowledgebase/Article/{article_id}/Revision`` (and the language-scoped
variant). Revisions are read-only, so this module exposes only a ``Get``
model. ``content`` is exchanged as HTML (``format: html``) and round-trips
Markdown on the model boundary.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef
from glpi_python_client.models.api_schema._content import GlpiMarkdownContent


class GetKBArticleRevision(GlpiModel):
    """Response shape returned by ``GET`` on KB revision endpoints.

    Mirrors ``components.schemas.KBArticleRevision``.
    """

    id: int | None = None
    kbarticle: IdNameRef | None = None
    revision: int | None = None
    name: str | None = None
    content: GlpiMarkdownContent = None
    language: str | None = None
    user: IdNameRef | None = None
    date: datetime | None = None


__all__ = ["GetKBArticleRevision"]
