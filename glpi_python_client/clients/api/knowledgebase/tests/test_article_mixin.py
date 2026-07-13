"""Recorder-based unit tests for ``KBArticleMixin``."""

from __future__ import annotations

from typing import Any

import pytest

from glpi_python_client import GlpiClient, IdNameRef, PatchKBArticle, PostKBArticle
from glpi_python_client.testing.utils import FakeResponse, make_client


class _FakeV1:
    """Stand-in for GLPIV1Session recording ``request_json`` calls."""

    def __init__(self, *, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._error = error

    def request_json(
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


class _Recorder:
    """Transport recorder returning canned FakeResponse objects."""

    def __init__(self, *, get_payload: Any = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._get_payload = get_payload if get_payload is not None else []

    def install(self, client: GlpiClient) -> None:
        def _get(
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

        def _post(
            endpoint: str,
            json_body: dict[str, Any] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            self.calls.append(
                {"method": "POST", "endpoint": endpoint, "json": json_body}
            )
            return FakeResponse(status_code=201, payload={"id": 88})

        def _patch(
            endpoint: str, json_body: dict[str, Any] | None = None
        ) -> FakeResponse:
            self.calls.append(
                {"method": "PATCH", "endpoint": endpoint, "json": json_body}
            )
            return FakeResponse(status_code=204, payload={})

        def _delete(
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


@pytest.fixture
def client() -> GlpiClient:
    return make_client()


def test_search_kb_articles_forwards_params(client: GlpiClient) -> None:
    rec = _Recorder(get_payload=[{"id": 1, "name": "Reset", "content": "<p>c</p>"}])
    rec.install(client)
    result = client.search_kb_articles(
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


def test_get_kb_article_targets_per_id_endpoint(client: GlpiClient) -> None:
    rec = _Recorder(get_payload={"id": 5, "name": "Reset", "content": "<p>c</p>"})
    rec.install(client)
    article = client.get_kb_article(5)
    assert article.id == 5
    assert rec.calls[0]["endpoint"] == "Knowledgebase/Article/5"


def test_create_kb_article_renders_markdown_and_returns_id(client: GlpiClient) -> None:
    rec = _Recorder()
    rec.install(client)
    new_id = client.create_kb_article(
        PostKBArticle(name="How to", content="Run **passwd**")
    )
    assert new_id == 88
    call = rec.calls[0]
    assert call["method"] == "POST"
    assert call["endpoint"] == "Knowledgebase/Article"
    assert call["json"]["name"] == "How to"
    assert "<strong>passwd</strong>" in call["json"]["content"]


def test_update_kb_article_sends_patch(client: GlpiClient) -> None:
    rec = _Recorder()
    rec.install(client)
    client.update_kb_article(5, PatchKBArticle(is_pinned=True))
    call = rec.calls[0]
    assert call["method"] == "PATCH"
    assert call["endpoint"] == "Knowledgebase/Article/5"
    assert call["json"] == {"is_pinned": True}


def test_delete_kb_article_with_force(client: GlpiClient) -> None:
    rec = _Recorder()
    rec.install(client)
    client.delete_kb_article(5, force=True)
    call = rec.calls[0]
    assert call["method"] == "DELETE"
    assert call["endpoint"] == "Knowledgebase/Article/5"
    assert call["json"] == {"force": True}


def test_set_kb_article_categories_writes_via_v1(client: GlpiClient) -> None:
    fake = _FakeV1()
    client._v1 = fake  # type: ignore[assignment]
    client.set_kb_article_categories(31, [14, 15])
    call = fake.calls[0]
    assert call["method"] == "PUT"
    assert call["path"] == "KnowbaseItem/31"
    assert call["json_body"] == {"input": {"_categories": [14, 15]}}


def test_set_kb_article_categories_empty_clears(client: GlpiClient) -> None:
    fake = _FakeV1()
    client._v1 = fake  # type: ignore[assignment]
    client.set_kb_article_categories(31, [])
    assert fake.calls[0]["json_body"] == {"input": {"_categories": []}}


def test_set_kb_article_categories_requires_v1(client: GlpiClient) -> None:
    assert client._v1 is None
    with pytest.raises(RuntimeError):
        client.set_kb_article_categories(31, [14])


def test_create_kb_article_applies_categories_via_v1(client: GlpiClient) -> None:
    rec = _Recorder()
    rec.install(client)
    fake = _FakeV1()
    client._v1 = fake  # type: ignore[assignment]
    new_id = client.create_kb_article(
        PostKBArticle(name="P", content="c", categories=[IdNameRef(id=14)])
    )
    assert new_id == 88
    assert rec.calls[0]["method"] == "POST"
    assert fake.calls[0]["path"] == "KnowbaseItem/88"
    assert fake.calls[0]["json_body"] == {"input": {"_categories": [14]}}


def test_create_kb_article_without_categories_skips_v1(client: GlpiClient) -> None:
    rec = _Recorder()
    rec.install(client)
    assert client._v1 is None  # no v1 configured
    new_id = client.create_kb_article(PostKBArticle(name="P", content="c"))
    assert new_id == 88  # no RuntimeError despite missing v1


def test_create_kb_article_category_failure_raises_without_rollback(
    client: GlpiClient,
) -> None:
    rec = _Recorder()
    rec.install(client)
    client._v1 = _FakeV1(error=ValueError("boom"))  # type: ignore[assignment]
    with pytest.raises(RuntimeError, match="88") as excinfo:
        client.create_kb_article(
            PostKBArticle(name="P", content="c", categories=[IdNameRef(id=14)])
        )
    # The article is NOT rolled back; the failure just raises, naming the id
    # and chaining the original error so the partial state is recoverable.
    assert not any(c["method"] == "DELETE" for c in rec.calls)
    assert isinstance(excinfo.value.__cause__, ValueError)
    assert "boom" in str(excinfo.value.__cause__)


def test_create_kb_article_ref_without_id_raises(client: GlpiClient) -> None:
    rec = _Recorder()
    rec.install(client)
    client._v1 = _FakeV1()  # type: ignore[assignment]
    with pytest.raises(RuntimeError, match="require an 'id'"):
        client.create_kb_article(
            PostKBArticle(name="P", content="c", categories=[IdNameRef(name="Parrots")])
        )
    assert not any(c["method"] == "DELETE" for c in rec.calls)


def test_create_kb_article_empty_categories_skips_v1(client: GlpiClient) -> None:
    rec = _Recorder()
    rec.install(client)
    assert client._v1 is None  # no v1 configured
    new_id = client.create_kb_article(
        PostKBArticle(name="P", content="c", categories=[])
    )
    assert new_id == 88  # empty list is a no-op on create; no v1 needed
    assert not any(c["method"] == "DELETE" for c in rec.calls)  # no legacy call


def test_update_kb_article_applies_categories_via_v1(client: GlpiClient) -> None:
    rec = _Recorder()
    rec.install(client)
    fake = _FakeV1()
    client._v1 = fake  # type: ignore[assignment]
    client.update_kb_article(5, PatchKBArticle(categories=[IdNameRef(id=14)]))
    assert rec.calls[0]["method"] == "PATCH"
    assert fake.calls[0]["path"] == "KnowbaseItem/5"
    assert fake.calls[0]["json_body"] == {"input": {"_categories": [14]}}


def test_update_kb_article_without_categories_skips_v1(client: GlpiClient) -> None:
    rec = _Recorder()
    rec.install(client)
    assert client._v1 is None
    client.update_kb_article(5, PatchKBArticle(is_pinned=True))  # no RuntimeError
    assert rec.calls[0]["method"] == "PATCH"


def test_update_kb_article_category_failure_does_not_roll_back(
    client: GlpiClient,
) -> None:
    rec = _Recorder()
    rec.install(client)
    client._v1 = _FakeV1(error=ValueError("boom"))  # type: ignore[assignment]
    with pytest.raises(ValueError, match="boom"):
        client.update_kb_article(5, PatchKBArticle(categories=[IdNameRef(id=14)]))
    # Update is intentionally non-atomic: the v2 patch stays, no rollback delete.
    assert not any(c["method"] == "DELETE" for c in rec.calls)
