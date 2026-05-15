"""Assistance entity schemas mirroring the ``/Assistance`` endpoints.

Ticket and Team-member schemas live at the top of this subpackage. Timeline
sub-resources (followups, tasks, solutions, document links) are grouped in
:mod:`.timeline`.
"""

from glpi_python_client.models.api_schema.assistance._team import (
    DeleteTeamMember,
    GetTeamMember,
    PatchTeamMember,
    PostTeamMember,
)
from glpi_python_client.models.api_schema.assistance._ticket import (
    DeleteTicket,
    GetTicket,
    PatchTicket,
    PostTicket,
)

__all__ = [
    "DeleteTeamMember",
    "DeleteTicket",
    "GetTeamMember",
    "GetTicket",
    "PatchTeamMember",
    "PatchTicket",
    "PostTeamMember",
    "PostTicket",
]
