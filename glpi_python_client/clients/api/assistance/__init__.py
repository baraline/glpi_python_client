"""GLPI ``/Assistance`` mixins for the Synchronous client."""

from __future__ import annotations

from glpi_python_client.clients.api.assistance._team import TeamMemberMixin
from glpi_python_client.clients.api.assistance._ticket import TicketMixin

__all__ = ["TeamMemberMixin", "TicketMixin"]
