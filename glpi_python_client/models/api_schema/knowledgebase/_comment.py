"""GLPI ``KBArticleComment`` schemas for the KB comment endpoints.

The endpoints live under
``/Knowledgebase/Article/{article_id}/Comment``. The field layout mirrors
``components.schemas.KBArticleComment`` from the GLPI OpenAPI contract
(2.3.0). The read-only ``id`` and ``parent`` references are excluded from
the request models, as is ``kbarticle`` (the parent article is implied by
the URL path). ``user.id`` is writable in the contract, so ``user`` is
exposed on the request models.
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

    The parent article (``kbarticle``) is taken from the URL path, and the
    contract marks the comment ``parent`` reference as read-only, so both
    are excluded. ``user.id`` is writable and may be set explicitly; the
    server defaults it to the current user when omitted.
    """

    user: IdNameRef | None = None
    language: str | None = None
    comment: str | None = None
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
