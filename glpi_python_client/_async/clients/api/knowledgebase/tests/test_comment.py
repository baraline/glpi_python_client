"""Recorder-based unit tests for ``KBArticleCommentMixin``."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import (
    PatchKBArticleComment,
    PostKBArticleComment,
)
from glpi_python_client._async._testing import FailingTransportRecorder
from glpi_python_client.testing.utils import FakeResponse


class _Recorder:
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
            return FakeResponse(status_code=201, payload={"id": 77})

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


async def test_list_kb_article_comments_targets_nested_endpoint(client: Any) -> None:
    rec = _Recorder(get_payload=[{"id": 1, "comment": "hi"}])
    rec.install(client)
    comments = await client.list_kb_article_comments(5)
    assert comments[0].id == 1
    assert rec.calls[0]["endpoint"] == "Knowledgebase/Article/5/Comment"


async def test_get_kb_article_comment_targets_per_id_endpoint(client: Any) -> None:
    rec = _Recorder(get_payload={"id": 7, "comment": "hi"})
    rec.install(client)
    comment = await client.get_kb_article_comment(5, 7)
    assert comment.id == 7
    assert rec.calls[0]["endpoint"] == "Knowledgebase/Article/5/Comment/7"


async def test_create_kb_article_comment_returns_id(client: Any) -> None:
    rec = _Recorder()
    rec.install(client)
    new_id = await client.create_kb_article_comment(
        5, PostKBArticleComment(comment="hi")
    )
    assert new_id == 77
    call = rec.calls[0]
    assert call["endpoint"] == "Knowledgebase/Article/5/Comment"
    assert call["json"] == {"comment": "hi"}


async def test_update_kb_article_comment_sends_patch(client: Any) -> None:
    rec = _Recorder()
    rec.install(client)
    await client.update_kb_article_comment(
        5, 7, PatchKBArticleComment(comment="edited")
    )
    call = rec.calls[0]
    assert call["method"] == "PATCH"
    assert call["endpoint"] == "Knowledgebase/Article/5/Comment/7"


async def test_delete_kb_article_comment_with_force(client: Any) -> None:
    rec = _Recorder()
    rec.install(client)
    await client.delete_kb_article_comment(5, 7, force=True)
    call = rec.calls[0]
    assert call["method"] == "DELETE"
    assert call["endpoint"] == "Knowledgebase/Article/5/Comment/7"
    assert call["json"] == {"force": True}


# ---------------------------------------------------------------------------
# Generic error handling (this mixin's share of the shared failure suites)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.list_kb_article_comments(1),
        lambda c: c.get_kb_article_comment(1, 2),
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
        lambda c: c.create_kb_article_comment(1, PostKBArticleComment(comment="x")),
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
        lambda c: c.update_kb_article_comment(1, 2, PatchKBArticleComment(comment="x")),
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
        lambda c: c.delete_kb_article_comment(1, 2, force=True),
    ],
)
async def test_delete_helpers_raise_on_failure(
    client: Any, call: Callable[[Any], Any]
) -> None:
    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        await call(client)
