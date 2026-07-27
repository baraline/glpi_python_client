"""GLPI ``/Assistance`` mixins for the GLPI client."""

from __future__ import annotations

from glpi_python_client._async.clients.api.assistance._team import TeamMemberMixin
from glpi_python_client._async.clients.api.assistance._ticket import TicketMixin

__all__ = ["TeamMemberMixin", "TicketMixin"]
