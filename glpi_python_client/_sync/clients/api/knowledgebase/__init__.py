"""GLPI ``/Knowledgebase`` mixins."""

from __future__ import annotations

from glpi_python_client._sync.clients.api.knowledgebase._article import KBArticleMixin
from glpi_python_client._sync.clients.api.knowledgebase._category import (
    KBCategoryMixin,
)
from glpi_python_client._sync.clients.api.knowledgebase._comment import (
    KBArticleCommentMixin,
)
from glpi_python_client._sync.clients.api.knowledgebase._revision import (
    KBArticleRevisionMixin,
)

__all__ = [
    "KBArticleCommentMixin",
    "KBArticleMixin",
    "KBArticleRevisionMixin",
    "KBCategoryMixin",
]
