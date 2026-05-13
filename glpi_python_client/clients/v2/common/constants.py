"""GLPI v2 endpoint names and shared type aliases.

This module keeps string constants and lightweight aliases in one place so the
client layers can share endpoint paths and request parameter types without
repeating literals.
"""

from __future__ import annotations

from typing import TypeAlias

GlpiId: TypeAlias = str | int
RequestParamValue: TypeAlias = str | int | float | bytes | None

TICKET_ENDPOINT = "Assistance/Ticket"
FOLLOWUP_SUFFIX = "Timeline/Followup"
TASK_SUFFIX = "Timeline/Task"
SOLUTION_SUFFIX = "Timeline/Solution"
DOCUMENT_SUFFIX = "Timeline/Document"
TEAM_MEMBER_SUFFIX = "TeamMember"
USER_ENDPOINT = "Administration/User"
LOCATION_ENDPOINT = "Dropdowns/Location"

LIST_TICKET_CORE_FIELDS = [
    "id",
    "name",
    "content",
    "is_deleted",
    "status",
    "urgency",
    "impact",
    "priority",
    "type",
    "external_id",
    "date_creation",
    "date_mod",
    "date_close",
    "category",
    "entity",
    "location",
    "request_type",
    "team",
    "user_recipient",
    "user_editor",
]
