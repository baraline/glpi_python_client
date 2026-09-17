"""Asset schemas mirroring the ``/Assets`` endpoints."""

from glpi_python_client.models.api_schema.assets._computer import (
    DeleteComputer,
    GetComputer,
    PatchComputer,
    PostComputer,
)

__all__ = [
    "DeleteComputer",
    "GetComputer",
    "PatchComputer",
    "PostComputer",
]
