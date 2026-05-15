"""GLPI ``/Assistance`` mixins for the asynchronous client."""

from __future__ import annotations

from glpi_python_client.clients.api.assistance._team import AsyncTeamMemberMixin
from glpi_python_client.clients.api.assistance._ticket import AsyncTicketMixin

__all__ = ["AsyncTeamMemberMixin", "AsyncTicketMixin"]
