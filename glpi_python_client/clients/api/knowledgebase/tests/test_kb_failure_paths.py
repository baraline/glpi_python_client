"""Failure-status branch coverage for the Knowledge base mixins."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import (
    GlpiClient,
    PatchKBArticle,
    PatchKBArticleComment,
    PatchKBCategory,
    PostKBArticle,
    PostKBArticleComment,
    PostKBCategory,
)
from glpi_python_client.testing.utils import FakeResponse, make_client


class _FailRecorder:
    """Transport stub returning a fixed non-success status for every verb."""

    def __init__(self, status: int) -> None:
        self.status = status

    def install(self, client: GlpiClient) -> None:
        def _resp(*args: Any, **kwargs: Any) -> FakeResponse:
            return FakeResponse(status_code=self.status, payload={"err": "x"})

        client._get_request = _resp  # type: ignore[method-assign]
        client._post_request = _resp  # type: ignore[method-assign]
        client._update_request = _resp  # type: ignore[method-assign]
        client._delete_request = _resp  # type: ignore[method-assign]


@pytest.fixture
def client() -> GlpiClient:
    return make_client()


_READ_CALLS: list[Callable[[GlpiClient], Any]] = [
    lambda c: c.get_kb_article(1),
    lambda c: c.get_kb_category(1),
    lambda c: c.list_kb_article_comments(1),
    lambda c: c.get_kb_article_comment(1, 2),
    lambda c: c.list_kb_article_revisions(1),
    lambda c: c.get_kb_article_revision(1, 2),
]

_WRITE_CALLS: list[Callable[[GlpiClient], Any]] = [
    lambda c: c.update_kb_article(1, PatchKBArticle(name="x")),
    lambda c: c.update_kb_category(1, PatchKBCategory(name="x")),
    lambda c: c.update_kb_article_comment(1, 2, PatchKBArticleComment(comment="x")),
]

_DELETE_CALLS: list[Callable[[GlpiClient], Any]] = [
    lambda c: c.delete_kb_article(1, force=True),
    lambda c: c.delete_kb_category(1, force=True),
    lambda c: c.delete_kb_article_comment(1, 2, force=True),
]

_CREATE_CALLS: list[Callable[[GlpiClient], Any]] = [
    lambda c: c.create_kb_article(PostKBArticle(name="x")),
    lambda c: c.create_kb_category(PostKBCategory(name="x")),
    lambda c: c.create_kb_article_comment(1, PostKBArticleComment(comment="x")),
]


@pytest.mark.parametrize("call", _READ_CALLS)
def test_read_helpers_raise_on_failure(client: GlpiClient, call: Callable) -> None:
    _FailRecorder(404).install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize("call", _CREATE_CALLS)
def test_create_helpers_raise_on_failure(client: GlpiClient, call: Callable) -> None:
    _FailRecorder(500).install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize("call", _WRITE_CALLS)
def test_update_helpers_raise_on_failure(client: GlpiClient, call: Callable) -> None:
    _FailRecorder(500).install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize("call", _DELETE_CALLS)
def test_delete_helpers_raise_on_failure(client: GlpiClient, call: Callable) -> None:
    _FailRecorder(500).install(client)
    with pytest.raises(ValueError):
        call(client)
