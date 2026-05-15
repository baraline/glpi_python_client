"""Dropdowns entity schemas mirroring the ``/Dropdowns`` endpoints."""

from glpi_python_client.models.api_schema.dropdowns._location import (
    DeleteLocation,
    GetLocation,
    PatchLocation,
    PostLocation,
)

__all__ = [
    "DeleteLocation",
    "GetLocation",
    "PatchLocation",
    "PostLocation",
]
