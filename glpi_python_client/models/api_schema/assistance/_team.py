"""GLPI ``TeamMember`` schemas for the ticket team-member endpoints.

The endpoints live under ``/Assistance/Ticket/{id}/TeamMember`` with
sub-routes ``/{role}/{itemtype}/{users_id}``. The field layout mirrors
``components.schemas.TeamMember`` from the GLPI OpenAPI contract.
"""

from __future__ import annotations

from glpi_python_client.models._base import GlpiModel


class GetTeamMember(GlpiModel):
    """Response shape returned by ``GET`` on ticket team-member endpoints.

    Mirrors ``components.schemas.TeamMember``.
    """

    id: int | None = None
    name: str | None = None
    type: str | None = None
    role: str | None = None


class PostTeamMember(GlpiModel):
    """Request body for ``POST`` on ticket team-member endpoints.

    Notes
    -----
    Mirrors ``components.schemas.TeamMember`` minus the read-only ``name``
    field. The OpenAPI contract marks ``id`` as ``readOnly`` on the request
    body but the live GLPI server still requires the target user's ``id``
    to identify the team member, so we expose it here.
    """

    id: int | None = None
    type: str | None = None
    role: str | None = None


class PatchTeamMember(PostTeamMember):
    """Request body for ``PATCH`` on ticket team-member endpoints."""


class DeleteTeamMember(GlpiModel):
    """Placeholder body for ``DELETE`` on ticket team-member endpoints.

    The contract advertises the role/itemtype/user identifiers as path
    parameters and exposes no body or query parameters; this empty model is
    kept for parity with the rest of the ``api_schema`` package.
    """


__all__ = [
    "DeleteTeamMember",
    "GetTeamMember",
    "PatchTeamMember",
    "PostTeamMember",
]
