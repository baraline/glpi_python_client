"""Administration entity schemas mirroring the ``/Administration`` endpoints.

This subpackage exposes the per-verb Pydantic models for ``User`` and
``Entity``. Each module follows the same ``Get<Name>``/``Post<Name>``/
``Patch<Name>``/``Delete<Name>`` naming convention.
"""

from glpi_python_client.models.api_schema.administration._entity import (
    DeleteEntity,
    GetEntity,
    PatchEntity,
    PostEntity,
)
from glpi_python_client.models.api_schema.administration._user import (
    DeleteUser,
    GetUser,
    PatchUser,
    PostUser,
)

__all__ = [
    "DeleteEntity",
    "DeleteUser",
    "GetEntity",
    "GetUser",
    "PatchEntity",
    "PatchUser",
    "PostEntity",
    "PostUser",
]
