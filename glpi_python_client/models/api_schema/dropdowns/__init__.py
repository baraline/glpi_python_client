"""Dropdowns entity schemas mirroring the ``/Dropdowns`` endpoints."""

from glpi_python_client.models.api_schema.dropdowns._contract_type import (
    DeleteContractType,
    GetContractType,
    PatchContractType,
    PostContractType,
)
from glpi_python_client.models.api_schema.dropdowns._location import (
    DeleteLocation,
    GetLocation,
    PatchLocation,
    PostLocation,
)

__all__ = [
    "DeleteContractType",
    "DeleteLocation",
    "GetContractType",
    "GetLocation",
    "PatchContractType",
    "PatchLocation",
    "PostContractType",
    "PostLocation",
]
