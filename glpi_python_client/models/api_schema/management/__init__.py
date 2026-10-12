"""Management entity schemas mirroring the ``/Management`` endpoints."""

from glpi_python_client.models.api_schema.management._contract import (
    DeleteContract,
    GetContract,
    PatchContract,
    PostContract,
)
from glpi_python_client.models.api_schema.management._contract_cost import (
    DeleteContractCost,
    GetContractCost,
    PatchContractCost,
    PostContractCost,
)
from glpi_python_client.models.api_schema.management._document import (
    DeleteDocument,
    GetDocument,
    PatchDocument,
    PostDocument,
)
from glpi_python_client.models.api_schema.management._document_item import (
    FollowupDocuments,
    GetDocumentItem,
)

__all__ = [
    "DeleteContract",
    "DeleteContractCost",
    "DeleteDocument",
    "FollowupDocuments",
    "GetContract",
    "GetContractCost",
    "GetDocument",
    "GetDocumentItem",
    "PatchContract",
    "PatchContractCost",
    "PatchDocument",
    "PostContract",
    "PostContractCost",
    "PostDocument",
]
