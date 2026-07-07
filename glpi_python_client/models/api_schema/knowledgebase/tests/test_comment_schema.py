"""Tests for the Knowledge base article comment api_schema models."""

from __future__ import annotations

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
    """The read-only ``id`` lands in ``extra_payload``."""

    comment = PostKBArticleComment.model_validate({"comment": "hi", "id": 9})
    assert comment.extra_payload == {"id": 9}


def test_patch_kb_article_comment_partial_body() -> None:
    """``PatchKBArticleComment`` accepts a partial body."""

    PatchKBArticleComment.model_validate({"comment": "edited"})


def test_delete_kb_article_comment_force_default() -> None:
    """``DeleteKBArticleComment`` exposes ``force`` as optional."""

    assert DeleteKBArticleComment().force is None
