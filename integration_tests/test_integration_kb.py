"""Integration tests for the Knowledge base endpoints.

These tests target a live GLPI instance and are skipped automatically when
the Knowledgebase API is not served (it was introduced in High-Level API
2.2.0; instances on 2.1.0 do not expose ``/Knowledgebase/*``). The probe
inspects the live ``/doc.json`` schema at session scope.

The assertions below were grounded against a live GLPI 2.3.0 instance:
create responses carry an ``id`` key, article ``content``/``description``
round-trip Markdown through GLPI's HTML storage, and the comment and
revision list endpoints return flat arrays (no timeline envelope).
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

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
def test_kb_category_full_crud(client: GlpiClient) -> None:
    """Exercise every category helper: create, get, update, search, delete."""

    suffix = _suffix()
    name = f"itest-kbcat-{suffix}"
    category_id = client.create_kb_category(PostKBCategory(name=name))
    try:
        fetched = client.get_kb_category(category_id)
        assert fetched.id == category_id
        assert fetched.name == name

        client.update_kb_category(
            category_id, PatchKBCategory(comment="updated by integration test")
        )
        assert client.get_kb_category(category_id).comment == (
            "updated by integration test"
        )

        matches = client.search_kb_categories(f"name=={name}")
        assert any(c.id == category_id for c in matches)
    finally:
        client.delete_kb_category(category_id, force=True)

    # After a forced delete the record is gone, so a fetch must fail.
    with pytest.raises(ValueError):
        client.get_kb_category(category_id)


@pytest.mark.usefixtures("kb_available")
def test_kb_article_full_crud_and_markdown(client: GlpiClient) -> None:
    """Create/get/update/search/delete an article and check Markdown round-trip."""

    suffix = _suffix()
    name = f"itest-kb-{suffix}"
    article_id = client.create_kb_article(
        PostKBArticle(
            name=name,
            content="Run **passwd** then check `logs`.",
            description="A *short* summary.",
            is_faq=True,
        )
    )
    try:
        fetched = client.get_kb_article(article_id)
        assert fetched.id == article_id
        assert fetched.is_faq is True
        # Markdown round-trips through GLPI's HTML storage: the client
        # receives HTML and normalises it back to the Markdown we sent.
        assert fetched.content is not None
        assert "**passwd**" in fetched.content
        assert "`logs`" in fetched.content
        assert "<strong>" not in fetched.content
        assert fetched.description is not None
        assert "*short*" in fetched.description

        client.update_kb_article(
            article_id,
            PatchKBArticle(is_pinned=True, content="Updated: run **reset**."),
        )
        updated = client.get_kb_article(article_id)
        assert updated.is_pinned is True
        assert "**reset**" in (updated.content or "")

        by_name = client.search_kb_articles(f"name=={name}")
        assert any(a.id == article_id for a in by_name)
        # The FAQ filter returns a non-empty set including our new FAQ article.
        faq = client.search_kb_articles("is_faq==1", limit=50)
        assert any(a.id == article_id for a in faq)
    finally:
        client.delete_kb_article(article_id, force=True)

    with pytest.raises(ValueError):
        client.get_kb_article(article_id)


@pytest.mark.usefixtures("kb_available")
def test_kb_article_comment_full_crud(client: GlpiClient) -> None:
    """Exercise every comment helper: create, list, get, update, delete."""

    suffix = _suffix()
    article_id = client.create_kb_article(
        PostKBArticle(name=f"itest-kb-comments-{suffix}", content="Body.")
    )
    try:
        comment_id = client.create_kb_article_comment(
            article_id, PostKBArticleComment(comment=f"first comment {suffix}")
        )
        listed = client.list_kb_article_comments(article_id)
        assert any(c.id == comment_id for c in listed)

        fetched = client.get_kb_article_comment(article_id, comment_id)
        assert fetched.id == comment_id
        assert f"first comment {suffix}" in (fetched.comment or "")

        client.update_kb_article_comment(
            article_id, comment_id, PatchKBArticleComment(comment="edited comment")
        )
        assert (
            client.get_kb_article_comment(article_id, comment_id).comment
            == "edited comment"
        )

        client.delete_kb_article_comment(article_id, comment_id, force=True)
        remaining = client.list_kb_article_comments(article_id)
        assert all(c.id != comment_id for c in remaining)
    finally:
        client.delete_kb_article(article_id, force=True)


@pytest.mark.usefixtures("kb_available")
def test_kb_article_revisions(client: GlpiClient) -> None:
    """List article revisions and fetch a single revision by number."""

    suffix = _suffix()
    article_id = client.create_kb_article(
        PostKBArticle(
            name=f"itest-kb-rev-{suffix}",
            content="Original **body** with `code`.",
        )
    )
    try:
        # Editing the article produces at least the initial revision.
        client.update_kb_article(
            article_id, PatchKBArticle(content="Revised **body**.")
        )
        revisions = client.list_kb_article_revisions(article_id)
        assert len(revisions) >= 1

        target = revisions[0].revision
        assert target is not None
        single = client.get_kb_article_revision(article_id, target)
        assert single.revision == target
        assert single.kbarticle is not None
        assert single.kbarticle.id == article_id
        # Revision content is also normalised from HTML to Markdown.
        assert single.content is not None
        assert "<strong>" not in single.content
    finally:
        client.delete_kb_article(article_id, force=True)
