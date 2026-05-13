"""Concrete GLPI model exports used by the high-level v2 clients.

This subpackage groups the rich ticket-related models that the client returns
and accepts when interacting with GLPI resources.
"""

from __future__ import annotations

from glpi_python_client.models.glpi._document import GlpiDocument
from glpi_python_client.models.glpi._followup import GlpiFollowup
from glpi_python_client.models.glpi._location import GlpiLocation
from glpi_python_client.models.glpi._solution import GlpiSolution
from glpi_python_client.models.glpi._task import GlpiTask
from glpi_python_client.models.glpi._team_member import GlpiTeamMember
from glpi_python_client.models.glpi._ticket import GlpiTicket
from glpi_python_client.models.glpi._user import GlpiUser

__all__ = [
    "GlpiDocument",
    "GlpiFollowup",
    "GlpiLocation",
    "GlpiSolution",
    "GlpiTask",
    "GlpiTeamMember",
    "GlpiTicket",
    "GlpiUser",
]
