"""Integration tests for the Knowledge base endpoints.

These tests target a live GLPI instance and are skipped automatically when
the Knowledgebase API is not served (it was introduced in High-Level API
2.2.0; instances on 2.1.0 do not expose ``/Knowledgebase/*``). The probe
inspects the live ``/doc.json`` schema at session scope.
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest

from glpi_python_client import (
    GlpiClient,
    PatchKBArticle,
    PostKBArticle,
    PostKBArticleComment,
    PostKBCategory,
)
from integration_tests.test_integration import _LiveGlpiConfig, _load_config

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def live_config() -> _LiveGlpiConfig:
    """Reuse the shared live-GLPI configuration loader."""

    return _load_config()


@pytest.fixture
def client(live_config: _LiveGlpiConfig) -> Iterator[GlpiClient]:
    """Yield one configured sync client and close it on teardown."""

    glpi_client = GlpiClient(
        glpi_api_url=live_config.api_url,
        client_id=live_config.client_id,
        client_secret=live_config.client_secret,
        username=live_config.username,
        password=live_config.password,
        glpi_entity=live_config.entity,
        glpi_profile=live_config.profile,
        entity_recursive=live_config.entity_recursive,
        verify_ssl=live_config.verify_ssl,
    )
    try:
        yield glpi_client
    finally:
        glpi_client.close()


@pytest.fixture
def kb_available(client: GlpiClient) -> None:
    """Skip the test when the live instance does not serve the KB API."""

    response = client._get_request("doc.json", skip_entity=True)
    paths = response.json().get("paths", {})
    if not any(str(path).startswith("/Knowledgebase") for path in paths):
        version = response.json().get("info", {}).get("version", "unknown")
        pytest.skip(
            "Knowledgebase API not served by this instance "
            f"(High-Level API {version}; needs >= 2.2.0)."
        )


def _suffix() -> str:
    return uuid4().hex[:12]


@pytest.mark.usefixtures("kb_available")
def test_kb_category_lifecycle(client: GlpiClient) -> None:
    """Create, fetch, and delete one knowledge base category."""

    suffix = _suffix()
    category_id = client.create_kb_category(
        PostKBCategory(name=f"itest-kbcat-{suffix}")
    )
    try:
        fetched = client.get_kb_category(category_id)
        assert fetched.id == category_id
    finally:
        client.delete_kb_category(category_id, force=True)


@pytest.mark.usefixtures("kb_available")
def test_kb_article_lifecycle(client: GlpiClient) -> None:
    """Create an article, edit it, add a comment, read revisions, delete."""

    suffix = _suffix()
    article_id = client.create_kb_article(
        PostKBArticle(
            name=f"itest-kb-{suffix}",
            content=f"Run **passwd** to reset ({suffix}).",
        )
    )
    try:
        fetched = client.get_kb_article(article_id)
        assert fetched.id == article_id
        assert "passwd" in (fetched.content or "")

        client.update_kb_article(article_id, PatchKBArticle(is_pinned=True))

        comment_id = client.create_kb_article_comment(
            article_id, PostKBArticleComment(comment=f"itest comment {suffix}")
        )
        comments = client.list_kb_article_comments(article_id)
        assert any(c.id == comment_id for c in comments)

        revisions = client.list_kb_article_revisions(article_id)
        assert isinstance(revisions, list)

        results = client.search_kb_articles(f"name==itest-kb-{suffix}")
        assert any(a.id == article_id for a in results)
    finally:
        client.delete_kb_article(article_id, force=True)
