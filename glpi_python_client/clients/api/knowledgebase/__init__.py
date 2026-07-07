"""GLPI ``/Knowledgebase`` mixins for the Synchronous client."""

from __future__ import annotations

from glpi_python_client.clients.api.knowledgebase._article import KBArticleMixin
from glpi_python_client.clients.api.knowledgebase._category import KBCategoryMixin
from glpi_python_client.clients.api.knowledgebase._comment import (
    KBArticleCommentMixin,
)

__all__ = ["KBArticleCommentMixin", "KBArticleMixin", "KBCategoryMixin"]
