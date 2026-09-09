"""GLPI ``KBArticle`` schemas for the ``/Knowledgebase/Article`` endpoints.

The field layout mirrors ``components.schemas.KBArticle`` from the GLPI
OpenAPI contract (2.3.0). ``content`` and ``description`` are both
exchanged as HTML (``format: html``). :class:`PostKBArticle` and
:class:`PatchKBArticle` accept Markdown and render it on serialisation;
:class:`GetKBArticle` stores the wire values in ``content_html`` and
``description_html`` and exposes Markdown through the ``content`` and
``description`` properties, converting on first read. See
:mod:`glpi_python_client.models.api_schema._content` for why the two
directions differ.

Server-managed fields (``id``, ``views``, ``revisions``, ``translations``)
are excluded from the request models; revisions and translations are
managed through the dedicated revision endpoints.
"""

from __future__ import annotations

from datetime import datetime
from functools import cached_property

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef
from glpi_python_client.models.api_schema._content import (
    GlpiMarkdownContent,
    GlpiRawContent,
    GlpiRawDescription,
    markdown_view,
)


class _KBArticleRevisionRef(GlpiModel):
    """One inline entry of the read-only ``KBArticle.revisions`` array."""

    id: int | None = None
    revision: int | None = None
    language: str | None = None
    date: datetime | None = None


class _KBArticleTranslationRef(GlpiModel):
    """One inline entry of the read-only ``KBArticle.translations`` array."""

    id: int | None = None
    language: str | None = None
    name: str | None = None


class GetKBArticle(GlpiModel):
    """Response shape returned by ``GET /Knowledgebase/Article`` endpoints.

    Mirrors ``components.schemas.KBArticle``. ``content_html`` and
    ``description_html`` hold the HTML exactly as GLPI sent it, and both
    accept their wire spellings (``content``, ``description``) as well; the
    :attr:`content` and :attr:`description` properties convert to Markdown
    on first read.

    An article body is the largest content GLPI serves, and searching the
    knowledge base returns whole articles, so this is the model where
    converting only what is read matters most.
    """

    id: int | None = None
    name: str | None = None
    content_html: GlpiRawContent = None
    categories: list[IdNameRef] | None = None
    is_faq: bool | None = None
    entity: IdNameRef | None = None
    is_recursive: bool | None = None
    user: IdNameRef | None = None
    views: int | None = None
    show_in_service_catalog: bool | None = None
    description_html: GlpiRawDescription = None
    illustration: str | None = None
    is_pinned: bool | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    date_begin: datetime | None = None
    date_end: datetime | None = None
    revisions: list[_KBArticleRevisionRef] | None = None
    translations: list[_KBArticleTranslationRef] | None = None

    @cached_property
    def content(self) -> str | None:
        """The article body as Markdown, or ``None`` if GLPI sent none.

        Converted from ``content_html`` on the first read and cached, so
        searching the knowledge base costs nothing per body and a body that
        cannot be converted affects only this record. ``content_html``
        holds the HTML exactly as it arrived.
        """

        return markdown_view(self.content_html)

    @cached_property
    def description(self) -> str | None:
        """The article summary as Markdown, or ``None`` if GLPI sent none.

        The short counterpart to :attr:`content`, converted from
        ``description_html`` on the first read and cached the same way.
        """

        return markdown_view(self.description_html)


class PostKBArticle(GlpiModel):
    """Request body for ``POST /Knowledgebase/Article``.

    Server-managed fields are excluded: ``id`` (``readOnly``), ``views``
    (a server-side counter), and the ``revisions``/``translations`` history
    arrays. The contract marks ``user.id`` as writable (the article author),
    so ``user`` is exposed here even though the server defaults it to the
    current user when omitted.

    ``categories`` looks writable but the GLPI 2.3.0 v2 API drops it (the
    nested ``id`` is ``readOnly``). ``GlpiClient.create_kb_article`` /
    ``update_kb_article`` apply it through a legacy fallback
    (``set_kb_article_categories``), which needs a configured v1 session
    pointing at the legacy ``apirest.php``.
    """

    name: str | None = None
    content: GlpiMarkdownContent = None
    categories: list[IdNameRef] | None = None
    is_faq: bool | None = None
    entity: IdNameRef | None = None
    is_recursive: bool | None = None
    user: IdNameRef | None = None
    show_in_service_catalog: bool | None = None
    description: GlpiMarkdownContent = None
    illustration: str | None = None
    is_pinned: bool | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    date_begin: datetime | None = None
    date_end: datetime | None = None


class PatchKBArticle(PostKBArticle):
    """Request body for ``PATCH /Knowledgebase/Article/{article_id}``.

    Inherits every writable field from :class:`PostKBArticle`.
    """


class DeleteKBArticle(GlpiModel):
    """Body for ``DELETE /Knowledgebase/Article/{article_id}``.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the article instead of moving
        the record to the GLPI trash.
    """

    force: bool | None = None


__all__ = [
    "DeleteKBArticle",
    "GetKBArticle",
    "PatchKBArticle",
    "PostKBArticle",
]
