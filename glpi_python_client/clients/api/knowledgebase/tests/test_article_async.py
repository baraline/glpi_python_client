"""Async-client tests for KB article category assignment.

The v2 API cannot write KB categories, so create/update apply them through
the legacy v1 ``_categories`` fallback. That fallback runs through the
public ``set_kb_article_categories``, which the async bridge wraps into a
coroutine — so without an override the category write is silently dropped
and the article is created with no category at all.
"""

from __future__ import annotations

from typing import Any

import pytest

from glpi_python_client import AsyncGlpiClient, PatchKBArticle, PostKBArticle
from glpi_python_client.models.api_schema._common import IdNameRef
from glpi_python_client.testing.utils import FakeResponse, make_async_client


class _FakeV1:
    """Stand-in for ``GLPIV1Session`` recording ``request_json`` calls."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, object] | None = None,
        json_body: dict[str, object] | None = None,
        success_statuses: tuple[int, ...] = (200, 201, 204, 206),
        failure_message: str | None = None,
    ) -> object:
        self.calls.append({"method": method, "path": path, "json_body": json_body})
        return [{"1": True, "message": ""}]


@pytest.fixture
def client() -> AsyncGlpiClient:
    """Return an async client with the v2 transport stubbed out.

    Both stubs record every ``json_body`` they receive (on the ``post_bodies``
    / ``patch_bodies`` attributes attached to the client) so tests can assert
    that stripping ``categories`` for the legacy fallback left the rest of
    the v2 request body untouched.
    """

    c = make_async_client()
    post_bodies: list[dict[str, object] | None] = []
    patch_bodies: list[dict[str, object] | None] = []

    def _post(
        endpoint: str,
        json_body: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> FakeResponse:
        post_bodies.append(json_body)
        return FakeResponse(status_code=201, payload={"id": 42})

    def _patch(
        endpoint: str, json_body: dict[str, object] | None = None
    ) -> FakeResponse:
        patch_bodies.append(json_body)
        return FakeResponse(status_code=200, payload={"id": 42})

    c._post_request = _post  # type: ignore[assignment]
    c._update_request = _patch  # type: ignore[assignment]
    c.post_bodies = post_bodies  # type: ignore[attr-defined]
    c.patch_bodies = patch_bodies  # type: ignore[attr-defined]
    return c


async def test_create_kb_article_links_categories(client: AsyncGlpiClient) -> None:
    """Creating with categories must actually issue the v1 category write."""

    fake = _FakeV1()
    client._v1 = fake  # type: ignore[assignment]

    new_id = await client.create_kb_article(
        PostKBArticle(name="t", answer="a", categories=[IdNameRef(id=7, name="cat")])
    )

    assert new_id == 42
    assert fake.calls == [
        {
            "method": "PUT",
            "path": "KnowbaseItem/42",
            "json_body": {"input": {"_categories": [7]}},
        }
    ]
    # The stripped v2 body must still carry every other field: only
    # ``categories`` was removed before the worker-thread create call runs.
    # A ``model_copy(update=...)`` that nuked more than ``categories`` would
    # otherwise pass every other assertion in this file undetected.
    assert client.post_bodies == [{"name": "t", "answer": "a"}]  # type: ignore[attr-defined]


async def test_create_kb_article_without_categories_needs_no_v1(
    client: AsyncGlpiClient,
) -> None:
    """Omitting categories must not require a v1 session."""

    client._v1 = None
    assert await client.create_kb_article(PostKBArticle(name="t", answer="a")) == 42


async def test_create_kb_article_wraps_category_failure(
    client: AsyncGlpiClient,
) -> None:
    """A category failure after create raises RuntimeError naming the id."""

    client._v1 = None  # no v1 session -> the fallback raises RuntimeError

    with pytest.raises(RuntimeError, match="KB article 42 was created but"):
        await client.create_kb_article(
            PostKBArticle(
                name="t", answer="a", categories=[IdNameRef(id=7, name="cat")]
            )
        )


async def test_create_kb_article_wraps_missing_id_category(
    client: AsyncGlpiClient,
) -> None:
    """A category ref without an id is wrapped in the same ``RuntimeError``.

    ``_apply_category_fallback_async`` raises ``ValueError`` before ever
    touching a v1 session when a category reference has no ``id`` (see
    ``_article_async.py``). ``create_kb_article`` wraps every fallback
    failure — including this one — into ``RuntimeError``. This is the
    async copy of a branch already covered on the sync client; the two
    copies can drift independently, so this branch needs its own test
    rather than relying on sync coverage.
    """

    with pytest.raises(RuntimeError, match="KB article 42 was created but"):
        await client.create_kb_article(
            PostKBArticle(name="t", answer="a", categories=[IdNameRef(name="cat")])
        )


async def test_update_kb_article_links_categories(client: AsyncGlpiClient) -> None:
    """Updating with a non-empty list must issue the v1 category write.

    This is the update-path counterpart of
    ``test_create_kb_article_links_categories``. Without it, the
    non-empty-list case on ``update_kb_article`` is only covered by
    composition: the ``[]`` test below proves the update path fires the
    legacy fallback at all, and the create test proves the id-collection
    loop works, but neither proves a non-empty list on *update*, the
    headline regression this branch fixed, actually reaches the v1
    ``PUT``.
    """

    fake = _FakeV1()
    client._v1 = fake  # type: ignore[assignment]

    await client.update_kb_article(
        42, PatchKBArticle(name="t3", categories=[IdNameRef(id=7, name="cat")])
    )

    assert fake.calls == [
        {
            "method": "PUT",
            "path": "KnowbaseItem/42",
            "json_body": {"input": {"_categories": [7]}},
        }
    ]
    # The stripped v2 patch body must still carry every other field: only
    # ``categories`` was removed before the worker-thread update call runs.
    assert client.patch_bodies == [{"name": "t3"}]  # type: ignore[attr-defined]


async def test_update_kb_article_clears_categories(client: AsyncGlpiClient) -> None:
    """An empty list clears every category through the v1 fallback."""

    fake = _FakeV1()
    client._v1 = fake  # type: ignore[assignment]

    await client.update_kb_article(42, PatchKBArticle(name="t2", categories=[]))

    assert fake.calls == [
        {
            "method": "PUT",
            "path": "KnowbaseItem/42",
            "json_body": {"input": {"_categories": []}},
        }
    ]
    # The stripped v2 patch body must still carry every other field: only
    # ``categories`` was removed before the worker-thread update call runs.
    # A ``model_copy(update=...)`` that nuked more than ``categories`` would
    # otherwise pass every other assertion in this file undetected.
    assert client.patch_bodies == [{"name": "t2"}]  # type: ignore[attr-defined]


async def test_update_kb_article_raises_on_missing_id_category(
    client: AsyncGlpiClient,
) -> None:
    """A category ref without an id raises the raw ``ValueError`` on update.

    Unlike ``create_kb_article``, ``update_kb_article`` does not wrap the
    fallback call in a ``try``/``except``: the v2 patch has already been
    applied by the time categories are assigned, so there is nothing to
    roll back and no article-was-created message to build around. The raw
    ``ValueError`` from ``_apply_category_fallback_async`` must therefore
    propagate unchanged.
    """

    with pytest.raises(ValueError, match="require an 'id'"):
        await client.update_kb_article(
            42, PatchKBArticle(name="t2", categories=[IdNameRef(name="cat")])
        )


async def test_update_kb_article_without_categories_skips_v1(
    client: AsyncGlpiClient,
) -> None:
    """``categories=None`` leaves categories untouched and calls no v1."""

    fake = _FakeV1()
    client._v1 = fake  # type: ignore[assignment]

    await client.update_kb_article(42, PatchKBArticle(name="t2"))

    assert fake.calls == []
