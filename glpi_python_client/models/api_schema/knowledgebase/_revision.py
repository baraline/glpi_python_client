"""GLPI ``KBArticleRevision`` schema for the KB revision endpoints.

The endpoints live under
``/Knowledgebase/Article/{article_id}/Revision`` (and the language-scoped
variant). Revisions are read-only, so this module exposes only a ``Get``
model. ``content`` is exchanged as HTML (``format: html``): the wire value
is stored in ``content_html`` and the ``content`` property converts it to
Markdown on first read. See
:mod:`glpi_python_client.models.api_schema._content` for why.
"""

from __future__ import annotations

from datetime import datetime
from functools import cached_property

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef
from glpi_python_client.models.api_schema._content import (
    GlpiRawContent,
    markdown_view,
)


class GetKBArticleRevision(GlpiModel):
    """Response shape returned by ``GET`` on KB revision endpoints.

    Mirrors ``components.schemas.KBArticleRevision``. ``content_html``
    holds the HTML exactly as GLPI sent it and also accepts the wire
    spelling ``content``; the :attr:`content` property converts it to
    Markdown on first read.

    Revision history is the clearest case for that: listing an article's
    revisions returns every past body, and a caller comparing dates or
    revision numbers reads none of them.
    """

    id: int | None = None
    kbarticle: IdNameRef | None = None
    revision: int | None = None
    name: str | None = None
    content_html: GlpiRawContent = None
    language: str | None = None
    user: IdNameRef | None = None
    date: datetime | None = None

    @cached_property
    def content(self) -> str | None:
        """The revision's body as Markdown, or ``None`` if GLPI sent none.

        Converted from ``content_html`` on the first read and cached.
        ``content_html`` holds the HTML exactly as it arrived.
        """

        return markdown_view(self.content_html)


__all__ = ["GetKBArticleRevision"]
