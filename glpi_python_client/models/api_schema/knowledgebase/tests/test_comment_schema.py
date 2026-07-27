"""Tests for the Knowledge base article comment api_schema models."""

from __future__ import annotations

from glpi_python_client._sync.clients.commons._payloads import model_to_payload
from glpi_python_client.models.api_schema._common import IdNameRef
from glpi_python_client.models.api_schema.knowledgebase import (
    DeleteKBArticleComment,
    GetKBArticleComment,
    PatchKBArticleComment,
    PostKBArticleComment,
)


def test_get_kb_article_comment_full_payload() -> None:
    """``GetKBArticleComment`` accepts every contract field."""

    payload = {
        "id": 7,
        "kbarticle": {"id": 5, "name": "Reset a password"},
        "user": {"id": 2, "name": "glpi"},
        "language": "en_GB",
        "comment": "This helped, thanks.",
        "parent": {"id": 0},
        "date_creation": "2026-01-02T09:00:00+00:00",
        "date_mod": "2026-01-03T09:00:00+00:00",
    }
    comment = GetKBArticleComment.model_validate(payload)
    assert comment.id == 7
    assert comment.kbarticle is not None
    assert comment.kbarticle.id == 5
    assert comment.comment == "This helped, thanks."


def test_post_kb_article_comment_routes_read_only_to_extra() -> None:
    """The read-only ``id`` and ``parent`` land in ``extra_payload``."""

    comment = PostKBArticleComment.model_validate(
        {"comment": "hi", "id": 9, "parent": {"id": 3}}
    )
    assert comment.extra_payload == {"id": 9, "parent": {"id": 3}}


def test_post_kb_article_comment_accepts_writable_user() -> None:
    """The contract marks ``user.id`` writable, so the author can be set."""

    body = model_to_payload(PostKBArticleComment(comment="hi", user=IdNameRef(id=2)))
    assert body["user"]["id"] == 2
    assert body["comment"] == "hi"


def test_patch_kb_article_comment_partial_body() -> None:
    """``PatchKBArticleComment`` accepts a partial body."""

    PatchKBArticleComment.model_validate({"comment": "edited"})


def test_delete_kb_article_comment_force_default() -> None:
    """``DeleteKBArticleComment`` exposes ``force`` as optional."""

    assert DeleteKBArticleComment().force is None
