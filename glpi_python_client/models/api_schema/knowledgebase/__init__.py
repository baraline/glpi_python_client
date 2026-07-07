"""Knowledge base entity schemas mirroring the ``/Knowledgebase`` endpoints.

This subpackage exposes the per-verb Pydantic models for KB articles,
article comments, article revisions, and categories. Each module follows
the ``Get<Name>``/``Post<Name>``/``Patch<Name>``/``Delete<Name>`` naming
convention. Revisions are read-only and expose a ``Get`` model only.
"""

from glpi_python_client.models.api_schema.knowledgebase._article import (
    DeleteKBArticle,
    GetKBArticle,
    PatchKBArticle,
    PostKBArticle,
)
from glpi_python_client.models.api_schema.knowledgebase._category import (
    DeleteKBCategory,
    GetKBCategory,
    PatchKBCategory,
    PostKBCategory,
)
from glpi_python_client.models.api_schema.knowledgebase._comment import (
    DeleteKBArticleComment,
    GetKBArticleComment,
    PatchKBArticleComment,
    PostKBArticleComment,
)

__all__ = [
    "DeleteKBArticle",
    "DeleteKBArticleComment",
    "DeleteKBCategory",
    "GetKBArticle",
    "GetKBArticleComment",
    "GetKBCategory",
    "PatchKBArticle",
    "PatchKBArticleComment",
    "PatchKBCategory",
    "PostKBArticle",
    "PostKBArticleComment",
    "PostKBCategory",
]
