"""GLPI ``KBArticleComment`` schemas for the KB comment endpoints.

The endpoints live under
``/Knowledgebase/Article/{article_id}/Comment``. The field layout mirrors
``components.schemas.KBArticleComment`` from the GLPI OpenAPI contract
(2.3.0). The read-only ``id`` and the server-managed ``kbarticle``/``user``
references are excluded from the request models; the parent article is
implied by the URL path.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef, IdRef


class GetKBArticleComment(GlpiModel):
    """Response shape returned by ``GET`` on KB comment endpoints.

    Mirrors ``components.schemas.KBArticleComment``.
    """

    id: int | None = None
    kbarticle: IdNameRef | None = None
    user: IdNameRef | None = None
    language: str | None = None
    comment: str | None = None
    parent: IdRef | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None


class PostKBArticleComment(GlpiModel):
    """Request body for ``POST`` on KB comment endpoints.

    The parent article (``kbarticle``) is taken from the URL path and the
    author (``user``) is set by the server, so both are excluded here.
    """

    language: str | None = None
    comment: str | None = None
    parent: IdRef | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None


class PatchKBArticleComment(PostKBArticleComment):
    """Request body for ``PATCH`` on KB comment endpoints.

    Inherits every writable field from :class:`PostKBArticleComment`.
    """


class DeleteKBArticleComment(GlpiModel):
    """Body for ``DELETE`` on KB comment endpoints.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the comment instead of moving
        the record to the GLPI trash.
    """

    force: bool | None = None


__all__ = [
    "DeleteKBArticleComment",
    "GetKBArticleComment",
    "PatchKBArticleComment",
    "PostKBArticleComment",
]
