"""Tests for the read-only Knowledge base article revision model."""

from __future__ import annotations

from glpi_python_client.models.api_schema.knowledgebase import GetKBArticleRevision


def test_get_kb_article_revision_full_payload() -> None:
    """``GetKBArticleRevision`` accepts every contract field and normalises HTML."""

    payload = {
        "id": 11,
        "kbarticle": {"id": 5, "name": "Reset a password"},
        "revision": 2,
        "name": "Reset a password",
        "content": "<p>Run <code>passwd</code>.</p>",
        "language": "en_GB",
        "user": {"id": 2, "name": "glpi"},
        "date": "2026-01-03T09:00:00+00:00",
    }
    revision = GetKBArticleRevision.model_validate(payload)
    assert revision.revision == 2
    assert "passwd" in (revision.content or "")
    assert revision.kbarticle is not None
    assert revision.kbarticle.id == 5
