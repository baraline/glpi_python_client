"""GLPI ``/Knowledgebase/Article`` mixin.

The mixin exposes search, fetch, create, update, and delete helpers for the
GLPI knowledge base article resource using the contract-aligned
``api_schema`` models. Article ``content`` and ``description`` round-trip
Markdown through GLPI's HTML wire format transparently.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from glpi_python_client._sync.clients.commons._constants import (
    KB_ARTICLE_ENDPOINT,
    GlpiId,
)
from glpi_python_client._sync.clients.commons._transport import TransportMixin
from glpi_python_client._errors import GlpiValidationError
from glpi_python_client.models.api_schema._common import IdNameRef
from glpi_python_client.models.api_schema.knowledgebase._article import (
    DeleteKBArticle,
    GetKBArticle,
    PatchKBArticle,
    PostKBArticle,
)

_V1_CATEGORY_FEATURE_LABEL = "knowledge base category assignments"


class KBArticleMixin(TransportMixin):
    """CRUD helpers for ``/Knowledgebase/Article``."""

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
        return self._resource_list(
            KB_ARTICLE_ENDPOINT, GetKBArticle, params=params
        )

    def iter_search_kb_articles(
        self,
        rsql_filter: str = "",
        *,
        batch_size: int = 50,
        sort: str | None = None,
        language: str | None = None,
    ) -> Iterator[list[GetKBArticle]]:
        """Yield successive pages of GLPI knowledge base articles until exhausted.

        The generator drives pagination automatically by advancing the
        ``start`` offset after each batch. Iteration stops when the server
        returns fewer items than ``batch_size``, which signals the last page.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
            Empty by default, which lists every visible record.
        batch_size : int, optional
            Number of records requested per page (default 50). Acts as the
            ``limit`` parameter on each underlying :meth:`search_kb_articles`
            call.
        sort : str | None, optional
            ``sort`` query parameter forwarded as-is to each page request.
        language : str | None, optional
            GLPI language code forwarded to each page request to select
            a translated view.

        Yields
        ------
        list[GetKBArticle]
            One page per iteration. The last yielded batch may be shorter
            than ``batch_size``.
        """

        start = 0
        while True:
            batch = self.search_kb_articles(
                rsql_filter,
                limit=batch_size,
                start=start,
                sort=sort,
                language=language,
            )
            if batch:
                yield batch
            if len(batch) < batch_size:
                break
            start += batch_size

    def get_kb_article(self, article_id: GlpiId) -> GetKBArticle:
        """Fetch one knowledge base article by identifier.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        return self._resource_get(
            f"{KB_ARTICLE_ENDPOINT}/{article_id}",
            GetKBArticle,
            failure_message=f"Failed to get KB article {article_id}",
        )

    def create_kb_article(self, article: PostKBArticle) -> int:
        """Create one knowledge base article and return its new identifier.

        When ``article.categories`` is a non-empty list, the categories are
        applied through the legacy fallback (:meth:`set_kb_article_categories`)
        because the v2 API cannot write them; this requires a configured v1
        session. ``None`` or an empty list is skipped — a freshly created
        article has no categories to clear — so callers that omit categories
        never need a v1 session. The v2 create is not undone if the category
        assignment fails: the article already exists, so the failure raises a
        ``RuntimeError`` naming the new article id (chaining the original
        error) and leaves the article in place for you to re-assign categories.
        """

        new_id = self._resource_create(
            KB_ARTICLE_ENDPOINT,
            article,
            failure_message="Failed to create KB article",
            missing_message="GLPI KB article create response did not include an ID",
            log_message_factory=lambda new_id: f"GLPI API created KB article {new_id}",
        )
        # A new article has no categories to clear, so only a non-empty list
        # triggers the legacy fallback; ``None``/``[]`` are no-ops here.
        if article.categories:
            try:
                self._apply_category_fallback(new_id, article.categories)
            except Exception as exc:
                raise RuntimeError(
                    f"KB article {new_id} was created but assigning its "
                    f"categories failed: {exc}"
                ) from exc
        return new_id

    def update_kb_article(
        self, article_id: GlpiId, article: PatchKBArticle
    ) -> None:
        """Update one knowledge base article with a partial body.

        When ``article.categories`` is provided — including an empty list to
        clear every category — the categories are applied through the legacy
        fallback (:meth:`set_kb_article_categories`) after the v2 patch, because
        the v2 API cannot write them; this requires a configured v1 session.
        ``None`` (the default) leaves categories untouched. Unlike create,
        update is not rolled back on a category failure — the v2 field changes
        are already applied.
        """

        self._resource_update(
            f"{KB_ARTICLE_ENDPOINT}/{article_id}",
            article,
            failure_message=f"Failed to update KB article {article_id}",
            log_message=f"GLPI API updated KB article {article_id}",
        )
        self._apply_category_fallback(article_id, article.categories)

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

    def set_kb_article_categories(
        self, article_id: GlpiId, category_ids: Sequence[int]
    ) -> None:
        """Set the categories of one knowledge base article.

        GLPI 11 stores KB categories as a many-to-many relationship that the
        v2 API exposes as read-only (``KBArticle.categories[].id`` is
        ``readOnly``), so it silently drops category writes. This helper sets
        the underlying ``_categories`` field through the legacy v1 API, which
        requires ``v1_base_url``/``v1_user_token`` to be configured (pointing
        at the legacy ``apirest.php``).

        The supplied ids REPLACE the article's full category set; passing an
        empty sequence clears every category. Category ids are not validated
        against the server — an unknown id simply is not linked.

        Raises
        ------
        RuntimeError
            When no legacy v1 session is configured on the client.
        GlpiStatusError
            When the legacy API returns a non-success status.
        """

        v1 = self._require_v1_session(_V1_CATEGORY_FEATURE_LABEL)
        v1.request_json(
            "PUT",
            f"KnowbaseItem/{article_id}",
            json_body={"input": {"_categories": [int(c) for c in category_ids]}},
            failure_message=f"Failed to set categories on KB article {article_id}",
        )

    def _apply_category_fallback(
        self, article_id: GlpiId, categories: list[IdNameRef] | None
    ) -> None:
        """Apply ``categories`` through the legacy fallback when provided.

        No-op when ``categories`` is ``None``. An empty list clears every
        category (used by update); ``create_kb_article`` skips the empty case
        before calling this helper. Raises ``GlpiValidationError`` when a
        category reference lacks an ``id``.
        """

        if categories is None:
            return
        ids: list[int] = []
        for ref in categories:
            if ref.id is None:
                raise GlpiValidationError(
                    "KB article categories require an 'id' to be linked; got a "
                    "category reference without an id."
                )
            ids.append(ref.id)
        self.set_kb_article_categories(article_id, ids)


__all__ = ["KBArticleMixin"]
