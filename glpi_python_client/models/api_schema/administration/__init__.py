"""Administration entity schemas mirroring the ``/Administration`` endpoints.

This subpackage exposes the per-verb Pydantic models for ``User``,
``Entity`` and ``Group``. Each module follows the same
``Get<Name>``/``Post<Name>``/
``Patch<Name>``/``Delete<Name>`` naming convention.
"""

from glpi_python_client.models.api_schema.administration._entity import (
    DeleteEntity,
    GetEntity,
    PatchEntity,
    PostEntity,
)
from glpi_python_client.models.api_schema.administration._group import (
    DeleteGroup,
    GetGroup,
    PatchGroup,
    PostGroup,
)
from glpi_python_client.models.api_schema.administration._user import (
    DeleteUser,
    GetUser,
    PatchUser,
    PostUser,
)
from glpi_python_client.models.api_schema.administration._user_authorization import (
    UserAuthorization,
)

__all__ = [
    "DeleteEntity",
    "DeleteGroup",
    "DeleteUser",
    "GetEntity",
    "GetGroup",
    "GetUser",
    "PatchEntity",
    "PatchGroup",
    "PatchUser",
    "PostEntity",
    "PostGroup",
    "PostUser",
    "UserAuthorization",
]
