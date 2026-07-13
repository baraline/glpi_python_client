"""Synchronous GLPI ``/Knowledgebase/Article`` mixin.

The mixin exposes search, fetch, create, update, and delete helpers for the
GLPI knowledge base article resource using the contract-aligned
``api_schema`` models. Article ``content`` and ``description`` round-trip
Markdown through GLPI's HTML wire format transparently.
"""

from __future__ import annotations

from glpi_python_client.clients.commons._constants import (
    KB_ARTICLE_ENDPOINT,
    GlpiId,
)
from glpi_python_client.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema.knowledgebase._article import (
    DeleteKBArticle,
    GetKBArticle,
    PatchKBArticle,
    PostKBArticle,
)


class KBArticleMixin(TransportMixin):
    """Synchronous CRUD helpers for ``/Knowledgebase/Article``."""

    def search_kb_articles(
        self,
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
        language: str | None = None,
    ) -> list[GetKBArticle]:
        """Search GLPI knowledge base articles with an optional RSQL filter.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
        limit : int, optional
            Maximum number of records returned by the GLPI server.
        start : int, optional
            Zero-based offset of the first record returned.
        sort : str | None, optional
            ``sort`` query parameter forwarded as-is.
        language : str | None, optional
            GLPI language code forwarded as the ``language`` query
            parameter to select a translated view.

        Returns
        -------
        list[GetKBArticle]
            Articles matching the filter.
        """

        params: dict[str, object] = {"limit": limit, "start": start}
        if rsql_filter:
            params["filter"] = rsql_filter
        if sort:
            params["sort"] = sort
        if language:
            params["language"] = language
        return self._resource_list(KB_ARTICLE_ENDPOINT, GetKBArticle, params=params)

    def get_kb_article(self, article_id: GlpiId) -> GetKBArticle:
        """Fetch one knowledge base article by identifier.

        Raises
        ------
        ValueError
            If the GLPI server returns a non-success HTTP status.
        """

        return self._resource_get(
            f"{KB_ARTICLE_ENDPOINT}/{article_id}",
            GetKBArticle,
            failure_message=f"Failed to get KB article {article_id}",
        )

    def create_kb_article(self, article: PostKBArticle) -> int:
        """Create one knowledge base article and return its new identifier."""

        return self._resource_create(
            KB_ARTICLE_ENDPOINT,
            article,
            failure_message="Failed to create KB article",
            missing_message="GLPI KB article create response did not include an ID",
            log_message_factory=lambda new_id: f"GLPI API created KB article {new_id}",
        )

    def update_kb_article(self, article_id: GlpiId, article: PatchKBArticle) -> None:
        """Update one knowledge base article with a partial body."""

        self._resource_update(
            f"{KB_ARTICLE_ENDPOINT}/{article_id}",
            article,
            failure_message=f"Failed to update KB article {article_id}",
            log_message=f"GLPI API updated KB article {article_id}",
        )

    def delete_kb_article(
        self, article_id: GlpiId, *, force: bool | None = None
    ) -> None:
        """Delete one knowledge base article by identifier."""

        self._resource_delete(
            f"{KB_ARTICLE_ENDPOINT}/{article_id}",
            failure_message=f"Failed to delete KB article {article_id}",
            log_message=f"GLPI API deleted KB article {article_id}",
            force=force,
            delete_model_cls=DeleteKBArticle,
        )


__all__ = ["KBArticleMixin"]
