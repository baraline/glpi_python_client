"""Recorder-based unit tests for ``KBArticleMixin``."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import (
    GlpiValidationError,
    IdNameRef,
    PatchKBArticle,
    PostKBArticle,
)
from glpi_python_client._async._testing import FailingTransportRecorder
from glpi_python_client.testing.utils import FakeResponse


class _FakeV1:
    """Stand-in for GLPIV1Session recording ``request_json`` calls."""

    def __init__(self, *, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._error = error

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        success_statuses: tuple[int, ...] = (200, 201, 204, 206),
        failure_message: str | None = None,
    ) -> object:
        self.calls.append(
            {
                "method": method,
                "path": path,
                "json_body": json_body,
                "failure_message": failure_message,
            }
        )
        if self._error is not None:
            raise self._error
        return [{"1": True, "message": ""}]

    async def close(self) -> None:
        """No-op; the real session is closed with the client."""


class _Recorder:
    """Transport recorder returning canned FakeResponse objects."""

    def __init__(self, *, get_payload: Any = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._get_payload = get_payload if get_payload is not None else []

    def install(self, client: Any) -> None:
        async def _get(
            endpoint: str,
            params: dict[str, Any] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            self.calls.append(
                {
                    "method": "GET",
                    "endpoint": endpoint,
                    "params": params,
                    "skip_entity": skip_entity,
                }
            )
            return FakeResponse(status_code=200, payload=self._get_payload)

        async def _post(
            endpoint: str,
            json_body: dict[str, Any] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            self.calls.append(
                {"method": "POST", "endpoint": endpoint, "json": json_body}
            )
            return FakeResponse(status_code=201, payload={"id": 88})

        async def _patch(
            endpoint: str, json_body: dict[str, Any] | None = None
        ) -> FakeResponse:
            self.calls.append(
                {"method": "PATCH", "endpoint": endpoint, "json": json_body}
            )
            return FakeResponse(status_code=204, payload={})

        async def _delete(
            endpoint: str,
            json_body: dict[str, Any] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            self.calls.append(
                {"method": "DELETE", "endpoint": endpoint, "json": json_body}
            )
            return FakeResponse(status_code=204, payload={})

        client._get_request = _get  # type: ignore[method-assign]
        client._post_request = _post  # type: ignore[method-assign]
        client._update_request = _patch  # type: ignore[method-assign]
        client._delete_request = _delete  # type: ignore[method-assign]


async def test_search_kb_articles_forwards_params(client: Any) -> None:
    rec = _Recorder(get_payload=[{"id": 1, "name": "Reset", "content": "<p>c</p>"}])
    rec.install(client)
    result = await client.search_kb_articles(
        "is_faq==1", limit=3, start=1, sort="date_mod desc", language="en_GB"
    )
    assert result[0].id == 1
    call = rec.calls[0]
    assert call["endpoint"] == "Knowledgebase/Article"
    assert call["params"]["filter"] == "is_faq==1"
    assert call["params"]["limit"] == 3
    assert call["params"]["start"] == 1
    assert call["params"]["sort"] == "date_mod desc"
    assert call["params"]["language"] == "en_GB"


async def test_get_kb_article_targets_per_id_endpoint(client: Any) -> None:
    rec = _Recorder(get_payload={"id": 5, "name": "Reset", "content": "<p>c</p>"})
    rec.install(client)
    article = await client.get_kb_article(5)
    assert article.id == 5
    assert rec.calls[0]["endpoint"] == "Knowledgebase/Article/5"


async def test_create_kb_article_renders_markdown_and_returns_id(client: Any) -> None:
    rec = _Recorder()
    rec.install(client)
    new_id = await client.create_kb_article(
        PostKBArticle(name="How to", content="Run **passwd**")
    )
    assert new_id == 88
    call = rec.calls[0]
    assert call["method"] == "POST"
    assert call["endpoint"] == "Knowledgebase/Article"
    assert call["json"]["name"] == "How to"
    assert "<strong>passwd</strong>" in call["json"]["content"]


async def test_update_kb_article_sends_patch(client: Any) -> None:
    rec = _Recorder()
    rec.install(client)
    await client.update_kb_article(5, PatchKBArticle(is_pinned=True))
    call = rec.calls[0]
    assert call["method"] == "PATCH"
    assert call["endpoint"] == "Knowledgebase/Article/5"
    assert call["json"] == {"is_pinned": True}


async def test_delete_kb_article_with_force(client: Any) -> None:
    rec = _Recorder()
    rec.install(client)
    await client.delete_kb_article(5, force=True)
    call = rec.calls[0]
    assert call["method"] == "DELETE"
    assert call["endpoint"] == "Knowledgebase/Article/5"
    assert call["json"] == {"force": True}


async def test_set_kb_article_categories_writes_via_v1(client: Any) -> None:
    fake = _FakeV1()
    client._v1 = fake  # type: ignore[assignment]
    await client.set_kb_article_categories(31, [14, 15])
    call = fake.calls[0]
    assert call["method"] == "PUT"
    assert call["path"] == "KnowbaseItem/31"
    assert call["json_body"] == {"input": {"_categories": [14, 15]}}


async def test_set_kb_article_categories_empty_clears(client: Any) -> None:
    fake = _FakeV1()
    client._v1 = fake  # type: ignore[assignment]
    await client.set_kb_article_categories(31, [])
    assert fake.calls[0]["json_body"] == {"input": {"_categories": []}}


async def test_set_kb_article_categories_requires_v1(client: Any) -> None:
    assert client._v1 is None
    with pytest.raises(RuntimeError):
        await client.set_kb_article_categories(31, [14])


async def test_create_kb_article_applies_categories_via_v1(client: Any) -> None:
    rec = _Recorder()
    rec.install(client)
    fake = _FakeV1()
    client._v1 = fake  # type: ignore[assignment]
    new_id = await client.create_kb_article(
        PostKBArticle(name="P", content="c", categories=[IdNameRef(id=14)])
    )
    assert new_id == 88
    assert rec.calls[0]["method"] == "POST"
    assert fake.calls[0]["path"] == "KnowbaseItem/88"
    assert fake.calls[0]["json_body"] == {"input": {"_categories": [14]}}


async def test_create_kb_article_without_categories_skips_v1(client: Any) -> None:
    rec = _Recorder()
    rec.install(client)
    assert client._v1 is None  # no v1 configured
    new_id = await client.create_kb_article(PostKBArticle(name="P", content="c"))
    assert new_id == 88  # no RuntimeError despite missing v1


async def test_create_kb_article_category_failure_raises_without_rollback(
    client: Any,
) -> None:
    rec = _Recorder()
    rec.install(client)
    client._v1 = _FakeV1(error=ValueError("boom"))  # type: ignore[assignment]
    with pytest.raises(RuntimeError, match="88") as excinfo:
        await client.create_kb_article(
            PostKBArticle(name="P", content="c", categories=[IdNameRef(id=14)])
        )
    # The article is NOT rolled back; the failure just raises, naming the id
    # and chaining the original error so the partial state is recoverable.
    assert not any(c["method"] == "DELETE" for c in rec.calls)
    assert isinstance(excinfo.value.__cause__, ValueError)
    assert "boom" in str(excinfo.value.__cause__)


async def test_create_kb_article_ref_without_id_raises(client: Any) -> None:
    """``create_kb_article`` wraps the failure in ``RuntimeError`` (kept bare
    by design), chaining the underlying ``GlpiValidationError`` as its cause.
    """

    rec = _Recorder()
    rec.install(client)
    client._v1 = _FakeV1()  # type: ignore[assignment]
    with pytest.raises(RuntimeError, match="require an 'id'") as excinfo:
        await client.create_kb_article(
            PostKBArticle(name="P", content="c", categories=[IdNameRef(name="Parrots")])
        )
    assert not any(c["method"] == "DELETE" for c in rec.calls)
    assert isinstance(excinfo.value.__cause__, GlpiValidationError)
    assert isinstance(excinfo.value.__cause__, ValueError)


async def test_create_kb_article_empty_categories_skips_v1(client: Any) -> None:
    rec = _Recorder()
    rec.install(client)
    assert client._v1 is None  # no v1 configured
    new_id = await client.create_kb_article(
        PostKBArticle(name="P", content="c", categories=[])
    )
    assert new_id == 88  # empty list is a no-op on create; no v1 needed
    assert not any(c["method"] == "DELETE" for c in rec.calls)  # no legacy call


async def test_update_kb_article_applies_categories_via_v1(client: Any) -> None:
    rec = _Recorder()
    rec.install(client)
    fake = _FakeV1()
    client._v1 = fake  # type: ignore[assignment]
    await client.update_kb_article(5, PatchKBArticle(categories=[IdNameRef(id=14)]))
    assert rec.calls[0]["method"] == "PATCH"
    assert fake.calls[0]["path"] == "KnowbaseItem/5"
    assert fake.calls[0]["json_body"] == {"input": {"_categories": [14]}}


async def test_update_kb_article_without_categories_skips_v1(client: Any) -> None:
    rec = _Recorder()
    rec.install(client)
    assert client._v1 is None
    await client.update_kb_article(5, PatchKBArticle(is_pinned=True))  # no RuntimeError
    assert rec.calls[0]["method"] == "PATCH"


async def test_update_kb_article_category_failure_does_not_roll_back(
    client: Any,
) -> None:
    rec = _Recorder()
    rec.install(client)
    client._v1 = _FakeV1(error=ValueError("boom"))  # type: ignore[assignment]
    with pytest.raises(ValueError, match="boom"):
        await client.update_kb_article(5, PatchKBArticle(categories=[IdNameRef(id=14)]))
    # Update is intentionally non-atomic: the v2 patch stays, no rollback delete.
    assert not any(c["method"] == "DELETE" for c in rec.calls)


# ---------------------------------------------------------------------------
# Generic error handling (this mixin's share of the shared failure suites)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_kb_article(1),
    ],
)
async def test_read_helpers_raise_on_failure(
    client: Any, call: Callable[[Any], Any]
) -> None:
    FailingTransportRecorder(404).install(client)
    with pytest.raises(ValueError):
        await call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.create_kb_article(PostKBArticle(name="x")),
    ],
)
async def test_create_helpers_raise_on_failure(
    client: Any, call: Callable[[Any], Any]
) -> None:
    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        await call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.update_kb_article(1, PatchKBArticle(name="x")),
    ],
)
async def test_update_helpers_raise_on_failure(
    client: Any, call: Callable[[Any], Any]
) -> None:
    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        await call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.delete_kb_article(1, force=True),
    ],
)
async def test_delete_helpers_raise_on_failure(
    client: Any, call: Callable[[Any], Any]
) -> None:
    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        await call(client)


async def test_iter_search_kb_articles_yields_every_page(client: Any) -> None:
    """The generator advances ``start`` until a short page ends the walk."""

    from glpi_python_client.models.api_schema.knowledgebase import GetKBArticle

    pages = [[GetKBArticle(id=i) for i in range(3)], [GetKBArticle(id=99)]]
    starts: list[int] = []
    forwarded: dict[str, Any] = {}

    async def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
        language: str | None = None,
    ) -> list[GetKBArticle]:
        starts.append(start)
        forwarded["sort"] = sort
        index = start // limit
        return pages[index] if index < len(pages) else []

    client.search_kb_articles = fake_search  # type: ignore[method-assign]

    batches = [
        batch
        async for batch in client.iter_search_kb_articles(
            "name==x", batch_size=3, sort="name asc"
        )
    ]

    assert starts == [0, 3]
    assert [len(b) for b in batches] == [3, 1]
    assert forwarded["sort"] == "name asc"


async def test_iter_search_kb_articles_stops_on_a_single_short_page(
    client: Any,
) -> None:
    """One short page is the last page; no second request is made."""

    from glpi_python_client.models.api_schema.knowledgebase import GetKBArticle

    starts: list[int] = []

    async def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
        language: str | None = None,
    ) -> list[GetKBArticle]:
        starts.append(start)
        return [GetKBArticle(id=1)]

    client.search_kb_articles = fake_search  # type: ignore[method-assign]

    batches = [batch async for batch in client.iter_search_kb_articles(batch_size=50)]

    assert starts == [0]
    assert len(batches) == 1


async def test_iter_search_kb_articles_yields_nothing_when_empty(client: Any) -> None:
    """An empty first page yields no batch at all rather than one empty list."""

    from glpi_python_client.models.api_schema.knowledgebase import GetKBArticle

    async def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
        language: str | None = None,
    ) -> list[GetKBArticle]:
        return []

    client.search_kb_articles = fake_search  # type: ignore[method-assign]

    assert [batch async for batch in client.iter_search_kb_articles()] == []
