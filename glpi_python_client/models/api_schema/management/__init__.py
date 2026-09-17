"""Management entity schemas mirroring the ``/Management`` endpoints."""

from glpi_python_client.models.api_schema.management._contract import (
    DeleteContract,
    GetContract,
    PatchContract,
    PostContract,
)
from glpi_python_client.models.api_schema.management._document import (
    DeleteDocument,
    GetDocument,
    PatchDocument,
    PostDocument,
)

__all__ = [
    "DeleteContract",
    "DeleteDocument",
    "GetContract",
    "GetDocument",
    "PatchContract",
    "PatchDocument",
    "PostContract",
    "PostDocument",
]
