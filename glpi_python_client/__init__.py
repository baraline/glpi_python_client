"""Public import surface for the GLPI Python client package.

This module re-exports the supported high-level clients and typed GLPI models
so applications can import them from a single stable package root.
"""

from __future__ import annotations

from glpi_python_client.clients import AsyncGlpiClient, GlpiClient, GLPIV1Session
from glpi_python_client.models import (
    GlpiDocument,
    GlpiEntity,
    GlpiFollowup,
    GlpiLocation,
    GlpiPriority,
    GlpiSolution,
    GlpiTask,
    GlpiTeamMember,
    GlpiTicket,
    GlpiTicketContext,
    GlpiTicketStatus,
    GlpiTicketType,
    GlpiUser,
)

__version__ = "0.1.3"

__all__ = [
    "AsyncGlpiClient",
    "GLPIV1Session",
    "GlpiClient",
    "GlpiDocument",
    "GlpiEntity",
    "GlpiFollowup",
    "GlpiLocation",
    "GlpiPriority",
    "GlpiSolution",
    "GlpiTask",
    "GlpiTeamMember",
    "GlpiTicket",
    "GlpiTicketContext",
    "GlpiTicketStatus",
    "GlpiTicketType",
    "GlpiUser",
    "__version__",
]
