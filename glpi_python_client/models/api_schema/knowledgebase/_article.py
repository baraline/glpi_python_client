"""GLPI ``KBArticle`` schemas for the ``/Knowledgebase/Article`` endpoints.

The field layout mirrors ``components.schemas.KBArticle`` from the GLPI
OpenAPI contract (2.3.0). ``content`` and ``description`` are exchanged as
HTML (``format: html``) and use the transparent Markdown annotation.
Server-managed fields (``id``, ``views``, ``revisions``, ``translations``)
are excluded from the request models; revisions and translations are
managed through the dedicated revision endpoints.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef
from glpi_python_client.models.api_schema._content import GlpiMarkdownContent


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

    Mirrors ``components.schemas.KBArticle``. ``content`` and
    ``description`` round-trip Markdown through GLPI's HTML wire format.
    """

    id: int | None = None
    name: str | None = None
    content: GlpiMarkdownContent = None
    categories: list[IdNameRef] | None = None
    is_faq: bool | None = None
    entity: IdNameRef | None = None
    is_recursive: bool | None = None
    user: IdNameRef | None = None
    views: int | None = None
    show_in_service_catalog: bool | None = None
    description: GlpiMarkdownContent = None
    illustration: str | None = None
    is_pinned: bool | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    date_begin: datetime | None = None
    date_end: datetime | None = None
    revisions: list[_KBArticleRevisionRef] | None = None
    translations: list[_KBArticleTranslationRef] | None = None


class PostKBArticle(GlpiModel):
    """Request body for ``POST /Knowledgebase/Article``.

    Server-managed fields are excluded: ``id`` (``readOnly``), ``views``
    (a server-side counter), and the ``revisions``/``translations`` history
    arrays. The contract marks ``user.id`` as writable (the article author),
    so ``user`` is exposed here even though the server defaults it to the
    current user when omitted.
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
