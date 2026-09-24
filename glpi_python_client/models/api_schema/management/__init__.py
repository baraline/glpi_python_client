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

__all__ = [
    "DeleteContract",
    "DeleteContractCost",
    "DeleteDocument",
    "GetContract",
    "GetContractCost",
    "GetDocument",
    "PatchContract",
    "PatchContractCost",
    "PatchDocument",
    "PostContract",
    "PostContractCost",
    "PostDocument",
]
