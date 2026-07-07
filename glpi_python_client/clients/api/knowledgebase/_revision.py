"""Synchronous GLPI ``/Knowledgebase/Article/{id}/Revision`` mixin.

Revisions are read-only. The GLPI contract exposes both a default-language
listing (``.../Revision``) and a language-scoped listing
(``.../{language}/Revision``); this mixin folds both into two helpers that
take an optional ``language`` argument and build the matching path.
"""

from __future__ import annotations

from glpi_python_client.clients.commons._constants import (
    KB_ARTICLE_ENDPOINT,
    KB_REVISION_SUFFIX,
    GlpiId,
)
from glpi_python_client.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema.knowledgebase._revision import (
    GetKBArticleRevision,
)


class KBArticleRevisionMixin(TransportMixin):
    """Synchronous read helpers for KB article revisions."""

    def _revision_base(self, article_id: GlpiId, language: str | None) -> str:
        """Return the revision collection path, language-scoped when given."""

        if language:
            return f"{KB_ARTICLE_ENDPOINT}/{article_id}/{language}/{KB_REVISION_SUFFIX}"
        return f"{KB_ARTICLE_ENDPOINT}/{article_id}/{KB_REVISION_SUFFIX}"

    def list_kb_article_revisions(
        self, article_id: GlpiId, *, language: str | None = None
    ) -> list[GetKBArticleRevision]:
        """List revisions of one knowledge base article.

        Parameters
        ----------
        article_id : GlpiId
            Numeric identifier of the parent article.
        language : str | None, optional
            When provided, list revisions for that GLPI language code using
            the language-scoped contract path.
        """

        return self._resource_list(
            self._revision_base(article_id, language),
            GetKBArticleRevision,
            failure_message=f"Failed to list revisions for KB article {article_id}",
        )

    def get_kb_article_revision(
        self,
        article_id: GlpiId,
        revision: int,
        *,
        language: str | None = None,
    ) -> GetKBArticleRevision:
        """Fetch one revision of a knowledge base article by revision number."""

        return self._resource_get(
            f"{self._revision_base(article_id, language)}/{revision}",
            GetKBArticleRevision,
            failure_message=(
                f"Failed to get revision {revision} of KB article {article_id}"
            ),
        )


__all__ = ["KBArticleRevisionMixin"]
