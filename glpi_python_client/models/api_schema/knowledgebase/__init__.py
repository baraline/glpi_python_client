"""Knowledge base entity schemas mirroring the ``/Knowledgebase`` endpoints.

This subpackage exposes the per-verb Pydantic models for KB articles,
article comments, article revisions, and categories. Each module follows
the ``Get<Name>``/``Post<Name>``/``Patch<Name>``/``Delete<Name>`` naming
convention. Revisions are read-only and expose a ``Get`` model only.
"""

from glpi_python_client.models.api_schema.knowledgebase._category import (
    DeleteKBCategory,
    GetKBCategory,
    PatchKBCategory,
    PostKBCategory,
)

__all__ = [
    "DeleteKBCategory",
    "GetKBCategory",
    "PatchKBCategory",
    "PostKBCategory",
]
