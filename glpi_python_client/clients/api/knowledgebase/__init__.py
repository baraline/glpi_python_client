"""GLPI ``/Knowledgebase`` mixins for the Synchronous client."""

from __future__ import annotations

from glpi_python_client.clients.api.knowledgebase._article import KBArticleMixin
from glpi_python_client.clients.api.knowledgebase._article_async import (
    AsyncKBArticleMixin,
)
from glpi_python_client.clients.api.knowledgebase._category import KBCategoryMixin
from glpi_python_client.clients.api.knowledgebase._comment import (
    KBArticleCommentMixin,
)
from glpi_python_client.clients.api.knowledgebase._revision import (
    KBArticleRevisionMixin,
)

__all__ = [
    "AsyncKBArticleMixin",
    "KBArticleCommentMixin",
    "KBArticleMixin",
    "KBArticleRevisionMixin",
    "KBCategoryMixin",
]
