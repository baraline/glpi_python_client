"""Asset schemas mirroring the ``/Assets`` endpoints."""

from glpi_python_client.models.api_schema.assets._computer import (
    DeleteComputer,
    GetComputer,
    PatchComputer,
    PostComputer,
)
from glpi_python_client.models.api_schema.assets._contract_item import (
    DeleteContractItem,
    GetContractItem,
    PatchContractItem,
    PostContractItem,
)

__all__ = [
    "DeleteComputer",
    "DeleteContractItem",
    "GetComputer",
    "GetContractItem",
    "PatchComputer",
    "PatchContractItem",
    "PostComputer",
    "PostContractItem",
]
