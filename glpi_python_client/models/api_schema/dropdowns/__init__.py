"""Dropdowns entity schemas mirroring the ``/Dropdowns`` endpoints."""

from glpi_python_client.models.api_schema.dropdowns._contract_type import (
    DeleteContractType,
    GetContractType,
    PatchContractType,
    PostContractType,
)
from glpi_python_client.models.api_schema.dropdowns._itil_category import (
    DeleteITILCategory,
    GetITILCategory,
    PatchITILCategory,
    PostITILCategory,
)
from glpi_python_client.models.api_schema.dropdowns._location import (
    DeleteLocation,
    GetLocation,
    PatchLocation,
    PostLocation,
)

__all__ = [
    "DeleteContractType",
    "DeleteITILCategory",
    "DeleteLocation",
    "GetContractType",
    "GetITILCategory",
    "GetLocation",
    "PatchContractType",
    "PatchITILCategory",
    "PatchLocation",
    "PostContractType",
    "PostITILCategory",
    "PostLocation",
]
