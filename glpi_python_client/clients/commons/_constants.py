"""GLPI v2 endpoint paths and shared transport-layer type aliases.

The constants here mirror the resource paths defined in the GLPI v2 API
contract under ``docs/glpi_api_contract.json``. Endpoint paths are kept in
one place so the API mixins all use the same resource locations and the
shared HTTP helpers can rely on stable parameter types.
"""

from __future__ import annotations

from typing import TypeAlias

GlpiId: TypeAlias = int
RequestParamValue: TypeAlias = str | int | float | bytes | None

# administration/
USER_ENDPOINT = "Administration/User"
ENTITY_ENDPOINT = "Administration/Entity"

# dropdowns/
LOCATION_ENDPOINT = "Dropdowns/Location"

# management/
DOCUMENT_ENDPOINT = "Management/Document"

# assistance/
TICKET_ENDPOINT = "Assistance/Ticket"
TEAM_MEMBER_SUFFIX = "TeamMember"

# assistance/timeline/
FOLLOWUP_SUFFIX = "Timeline/Followup"
TASK_SUFFIX = "Timeline/Task"
SOLUTION_SUFFIX = "Timeline/Solution"
TIMELINE_DOCUMENT_SUFFIX = "Timeline/Document"


__all__ = [
    "DOCUMENT_ENDPOINT",
    "ENTITY_ENDPOINT",
    "FOLLOWUP_SUFFIX",
    "LOCATION_ENDPOINT",
    "SOLUTION_SUFFIX",
    "TASK_SUFFIX",
    "TEAM_MEMBER_SUFFIX",
    "TICKET_ENDPOINT",
    "TIMELINE_DOCUMENT_SUFFIX",
    "USER_ENDPOINT",
    "GlpiId",
    "RequestParamValue",
]
