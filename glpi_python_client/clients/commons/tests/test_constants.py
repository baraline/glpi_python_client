"""Tests for the GLPI Knowledge base endpoint path constants."""

from __future__ import annotations

from glpi_python_client.clients.commons import _constants


def test_knowledgebase_endpoint_constants() -> None:
    """The KB endpoint constants match the 2.3.0 contract resource paths."""

    assert _constants.KB_ARTICLE_ENDPOINT == "Knowledgebase/Article"
    assert _constants.KB_CATEGORY_ENDPOINT == "Knowledgebase/Category"
    assert _constants.KB_COMMENT_SUFFIX == "Comment"
    assert _constants.KB_REVISION_SUFFIX == "Revision"
