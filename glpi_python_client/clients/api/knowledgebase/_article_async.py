"""Asynchronous overrides for KB article category assignment.

The v2 API exposes ``KBArticle.categories[].id`` as ``readOnly``, so
:meth:`create_kb_article` and :meth:`update_kb_article` apply categories
through the legacy v1 ``_categories`` fallback. That fallback calls the
public :meth:`set_kb_article_categories` through ``self``, which the async
bridge has wrapped into a coroutine — so the synchronous bodies drop the
call and the article silently keeps no categories.

These overrides strip ``categories`` from the model, run the untouched
synchronous v2 write in a worker thread (its own fallback then no-ops),
and apply the categories with an awaited call. Keeping the sync module
untouched makes the fix purely additive.

The mixin must sit **before** :class:`KBArticleMixin` in the
:class:`~glpi_python_client.clients.AsyncGlpiClient` base list.
"""

from __future__ import annotations

import asyncio

from glpi_python_client.clients.api.knowledgebase._article import KBArticleMixin
from glpi_python_client.clients.commons._constants import GlpiId
from glpi_python_client.models.api_schema._common import IdNameRef
from glpi_python_client.models.api_schema.knowledgebase._article import (
    PatchKBArticle,
    PostKBArticle,
)


class AsyncKBArticleMixin(KBArticleMixin):
    """Async overrides for the two KB article writes that set categories."""

    async def _apply_category_fallback_async(
        self, article_id: GlpiId, categories: list[IdNameRef] | None
    ) -> None:
        """Apply ``categories`` through the awaited legacy fallback.

        Mirrors :meth:`KBArticleMixin._apply_category_fallback` but awaits
        the bridge-wrapped :meth:`set_kb_article_categories`.

        Parameters
        ----------
        article_id : GlpiId
            Identifier of the article to re-categorise.
        categories : list[IdNameRef] | None
            Category references to link. ``None`` is a no-op; an empty
            list clears every category.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            When a category reference lacks an ``id``.
        """

        if categories is None:
            return
        ids: list[int] = []
        for ref in categories:
            if ref.id is None:
                raise ValueError(
                    "KB article categories require an 'id' to be linked; got a "
                    "category reference without an id."
                )
            ids.append(ref.id)
        # ``set_kb_article_categories`` is declared on ``KBArticleMixin``, the
        # very class this mixin subclasses, so mypy resolves it statically as
        # the synchronous ``-> None`` method rather than the bridge-generated
        # coroutine it becomes at runtime on ``AsyncGlpiClient``. That mismatch
        # is exactly what makes the await necessary here.
        await self.set_kb_article_categories(  # type: ignore[misc, func-returns-value]
            article_id, ids
        )

    async def create_kb_article(  # type: ignore[override]
        self, article: PostKBArticle
    ) -> int:
        """Create one knowledge base article and return its new identifier.

        Async override of :meth:`KBArticleMixin.create_kb_article`. The v2
        create runs in a worker thread with ``categories`` stripped, then
        the categories are applied through the awaited legacy fallback.
        Error semantics match the synchronous version: the create is not
        undone when the category assignment fails.

        Parameters
        ----------
        article : PostKBArticle
            Body of the article to create.

        Returns
        -------
        int
            Identifier assigned by GLPI.

        Raises
        ------
        RuntimeError
            When the article was created but assigning its categories
            failed. The message names the new article id.
        """

        stripped = article.model_copy(update={"categories": None})
        new_id: int = await asyncio.to_thread(
            KBArticleMixin.create_kb_article, self, stripped
        )
        if article.categories:
            try:
                await self._apply_category_fallback_async(new_id, article.categories)
            except Exception as exc:
                raise RuntimeError(
                    f"KB article {new_id} was created but assigning its "
                    f"categories failed: {exc}"
                ) from exc
        return new_id

    async def update_kb_article(  # type: ignore[override]
        self, article_id: GlpiId, article: PatchKBArticle
    ) -> None:
        """Update one knowledge base article with a partial body.

        Async override of :meth:`KBArticleMixin.update_kb_article`. The v2
        patch runs in a worker thread with ``categories`` stripped, then
        the categories are applied through the awaited legacy fallback.
        ``None`` leaves categories untouched; an empty list clears them.

        Parameters
        ----------
        article_id : GlpiId
            Identifier of the article to update.
        article : PatchKBArticle
            Partial body to apply.

        Returns
        -------
        None
        """

        stripped = article.model_copy(update={"categories": None})
        await asyncio.to_thread(
            KBArticleMixin.update_kb_article, self, article_id, stripped
        )
        await self._apply_category_fallback_async(article_id, article.categories)


__all__ = ["AsyncKBArticleMixin"]
