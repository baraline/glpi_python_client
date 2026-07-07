"""Recorder-based unit tests for ``KBArticleMixin``."""

from __future__ import annotations

from typing import Any

import pytest

from glpi_python_client import GlpiClient, PatchKBArticle, PostKBArticle
from glpi_python_client.testing.utils import FakeResponse, make_client


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
