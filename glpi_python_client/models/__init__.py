"""Public model exports for the GLPI client package.

The models are organised in two layers:

* :mod:`glpi_python_client.models.api_schema` -- raw Pydantic shapes that
  mirror ``docs/glpi_api_contract.json`` one for one. One model per HTTP
  verb is exposed under the ``Get<Name>``, ``Post<Name>``, ``Patch<Name>``
  and ``Delete<Name>`` naming convention. Use these models from new client
  mixins.
* :mod:`glpi_python_client.models.custom_schema` -- aggregated views, such
  as :class:`GlpiTicketContext`, that group several API objects into one
  richer payload.
"""

from __future__ import annotations

from glpi_python_client.models.api_schema._common import (
    IdNameCompletenameRef,
    IdNameRef,
    IdRef,
)
from glpi_python_client.models.api_schema.administration import (
    DeleteEntity,
    DeleteUser,
    GetEntity,
    GetUser,
    PatchEntity,
    PatchUser,
    PostEntity,
    PostUser,
)
from glpi_python_client.models.api_schema.assistance import (
    DeleteTeamMember,
    DeleteTicket,
    GetTeamMember,
    GetTicket,
    PatchTeamMember,
    PatchTicket,
    PostTeamMember,
    PostTicket,
)
from glpi_python_client.models.api_schema.assistance.timeline import (
    DeleteFollowup,
    DeleteSolution,
    DeleteTicketTask,
    DeleteTimelineDocument,
    GetFollowup,
    GetSolution,
    GetTicketTask,
    GetTimelineDocument,
    PatchFollowup,
    PatchSolution,
    PatchTicketTask,
    PatchTimelineDocument,
    PostFollowup,
    PostSolution,
    PostTicketTask,
    PostTimelineDocument,
)
from glpi_python_client.models.api_schema.dropdowns import (
    DeleteLocation,
    GetLocation,
    PatchLocation,
    PostLocation,
)
from glpi_python_client.models.api_schema.enums import (
    GlpiEnum,
    GlpiGlobalValidation,
    GlpiPriority,
    GlpiSolutionStatus,
    GlpiTaskState,
    GlpiTicketStatus,
    GlpiTicketType,
    GlpiTimelinePosition,
    GlpiUserAuthType,
)
from glpi_python_client.models.api_schema.management import (
    DeleteDocument,
    GetDocument,
    PatchDocument,
    PostDocument,
)
from glpi_python_client.models.custom_schema import (
    GlpiTicketContext,
    TicketMarkdownOptions,
)

__all__ = [
    "DeleteDocument",
    "DeleteEntity",
    "DeleteFollowup",
    "DeleteLocation",
    "DeleteSolution",
    "DeleteTeamMember",
    "DeleteTicket",
    "DeleteTicketTask",
    "DeleteTimelineDocument",
    "DeleteUser",
    "GetDocument",
    "GetEntity",
    "GetFollowup",
    "GetLocation",
    "GetSolution",
    "GetTeamMember",
    "GetTicket",
    "GetTicketTask",
    "GetTimelineDocument",
    "GetUser",
    "GlpiEnum",
    "GlpiGlobalValidation",
    "GlpiPriority",
    "GlpiSolutionStatus",
    "GlpiTaskState",
    "GlpiTicketContext",
    "GlpiTicketStatus",
    "GlpiTicketType",
    "GlpiTimelinePosition",
    "GlpiUserAuthType",
    "IdNameCompletenameRef",
    "IdNameRef",
    "IdRef",
    "PatchDocument",
    "PatchEntity",
    "PatchFollowup",
    "PatchLocation",
    "PatchSolution",
    "PatchTeamMember",
    "PatchTicket",
    "PatchTicketTask",
    "PatchTimelineDocument",
    "PatchUser",
    "PostDocument",
    "PostEntity",
    "PostFollowup",
    "PostLocation",
    "PostSolution",
    "PostTeamMember",
    "PostTicket",
    "PostTicketTask",
    "PostTimelineDocument",
    "PostUser",
    "TicketMarkdownOptions",
]
