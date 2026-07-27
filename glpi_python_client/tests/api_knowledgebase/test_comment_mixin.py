"""Recorder-based unit tests for ``KBArticleCommentMixin``."""

from __future__ import annotations

from typing import Any

import pytest

from glpi_python_client import (
    GlpiClient,
    PatchKBArticleComment,
    PostKBArticleComment,
)
from glpi_python_client.testing.utils import FakeResponse, make_client


class _Recorder:
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
            return FakeResponse(status_code=201, payload={"id": 77})

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


def test_list_kb_article_comments_targets_nested_endpoint(client: GlpiClient) -> None:
    rec = _Recorder(get_payload=[{"id": 1, "comment": "hi"}])
    rec.install(client)
    comments = client.list_kb_article_comments(5)
    assert comments[0].id == 1
    assert rec.calls[0]["endpoint"] == "Knowledgebase/Article/5/Comment"


def test_get_kb_article_comment_targets_per_id_endpoint(client: GlpiClient) -> None:
    rec = _Recorder(get_payload={"id": 7, "comment": "hi"})
    rec.install(client)
    comment = client.get_kb_article_comment(5, 7)
    assert comment.id == 7
    assert rec.calls[0]["endpoint"] == "Knowledgebase/Article/5/Comment/7"


def test_create_kb_article_comment_returns_id(client: GlpiClient) -> None:
    rec = _Recorder()
    rec.install(client)
    new_id = client.create_kb_article_comment(5, PostKBArticleComment(comment="hi"))
    assert new_id == 77
    call = rec.calls[0]
    assert call["endpoint"] == "Knowledgebase/Article/5/Comment"
    assert call["json"] == {"comment": "hi"}


def test_update_kb_article_comment_sends_patch(client: GlpiClient) -> None:
    rec = _Recorder()
    rec.install(client)
    client.update_kb_article_comment(5, 7, PatchKBArticleComment(comment="edited"))
    call = rec.calls[0]
    assert call["method"] == "PATCH"
    assert call["endpoint"] == "Knowledgebase/Article/5/Comment/7"


def test_delete_kb_article_comment_with_force(client: GlpiClient) -> None:
    rec = _Recorder()
    rec.install(client)
    client.delete_kb_article_comment(5, 7, force=True)
    call = rec.calls[0]
    assert call["method"] == "DELETE"
    assert call["endpoint"] == "Knowledgebase/Article/5/Comment/7"
    assert call["json"] == {"force": True}
