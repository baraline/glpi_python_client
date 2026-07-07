"""Tests for the Knowledge base article api_schema models."""

from __future__ import annotations

from glpi_python_client.clients.commons._payloads import model_to_payload
from glpi_python_client.models.api_schema.knowledgebase import (
    DeleteKBArticle,
    GetKBArticle,
    PatchKBArticle,
    PostKBArticle,
)


def test_get_kb_article_full_payload() -> None:
    """``GetKBArticle`` accepts every contract field of ``KBArticle``."""

    payload = {
        "id": 5,
        "name": "Reset a password",
        "content": "<p>Open the console and run <code>passwd</code>.</p>",
        "categories": [{"id": 4, "name": "Network"}],
        "is_faq": True,
        "entity": {"id": 0, "name": "root"},
        "is_recursive": True,
        "user": {"id": 2, "name": "glpi"},
        "views": 42,
        "show_in_service_catalog": False,
        "description": "<p>Short summary</p>",
        "illustration": "reset.png",
        "is_pinned": True,
        "date_creation": "2026-01-02T09:00:00+00:00",
        "date_mod": "2026-01-03T09:00:00+00:00",
        "date_begin": "2026-01-01T00:00:00+00:00",
        "date_end": "2026-12-31T00:00:00+00:00",
        "revisions": [
            {
                "id": 11,
                "revision": 2,
                "language": "en_GB",
                "date": "2026-01-03T09:00:00+00:00",
            }
        ],
        "translations": [{"id": 21, "language": "fr_FR", "name": "Reinitialiser"}],
    }
    article = GetKBArticle.model_validate(payload)
    assert article.id == 5
    # HTML content is normalised to Markdown on the model boundary.
    assert "passwd" in (article.content or "")
    assert article.categories is not None
    assert article.categories[0].id == 4
    assert article.revisions is not None
    assert article.revisions[0].revision == 2
    assert article.translations is not None
    assert article.translations[0].language == "fr_FR"


def test_post_kb_article_markdown_content_renders_html() -> None:
    """Markdown ``content`` is rendered back to HTML on serialisation."""

    article = PostKBArticle(name="How to", content="Run **passwd**")
    body = model_to_payload(article)
    assert body["name"] == "How to"
    assert "<strong>passwd</strong>" in body["content"]


def test_post_kb_article_routes_server_managed_fields_to_extra() -> None:
    """Server-managed fields land in ``extra_payload`` rather than typed slots."""

    for forbidden in ("id", "views"):
        article = PostKBArticle.model_validate({"name": "x", forbidden: 3})
        assert article.extra_payload == {forbidden: 3}


def test_patch_kb_article_partial_body() -> None:
    """``PatchKBArticle`` accepts a partial body."""

    PatchKBArticle.model_validate({"is_pinned": True})


def test_delete_kb_article_force_default() -> None:
    """``DeleteKBArticle`` exposes ``force`` as optional."""

    assert DeleteKBArticle().force is None
