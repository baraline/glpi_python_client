"""GLPI ``TeamMember`` schemas for the ticket team-member endpoints.

The endpoints live under ``/Assistance/Ticket/{id}/TeamMember`` with
sub-routes ``/{role}/{itemtype}/{users_id}``. The field layout mirrors
``components.schemas.TeamMember`` from the GLPI OpenAPI contract.
"""

from __future__ import annotations

from glpi_python_client.models._base import GlpiModel


class GetTeamMember(GlpiModel):
    """Response shape returned by ``GET`` on ticket team-member endpoints.

    Mirrors ``components.schemas.TeamMember``. No field carries a
    ``description`` in the OpenAPI contract; the parameters below are
    documented by field name and context.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier of the team-member link (``readOnly``).
    name : str | None, optional
        Display name of the actor (typically the user or group name).
    type : str | None, optional
        GLPI actor type, such as ``"User"`` or ``"Group"``.
    role : str | None, optional
        Ticket role assigned to the actor, such as ``"Requester"``,
        ``"Observer"`` or ``"Assigned to"``.
    """

    id: int | None = None
    name: str | None = None
    type: str | None = None
    role: str | None = None


class PostTeamMember(GlpiModel):
    """Request body for ``POST`` on ticket team-member endpoints.

    The contract marks ``id`` as ``readOnly`` on the schema definition,
    but the live GLPI server still requires the target actor's ``id``
    to identify the team member, so the field is exposed here.
    No field carries a ``description`` in the OpenAPI contract.

    Parameters
    ----------
    id : int | None, optional
        GLPI identifier of the actor to add (user or group ``id``).
    type : str | None, optional
        GLPI actor type, such as ``"User"`` or ``"Group"``.
    role : str | None, optional
        Ticket role to assign to the actor, such as ``"Requester"``,
        ``"Observer"`` or ``"Assigned to"``.
    """

    id: int | None = None
    type: str | None = None
    role: str | None = None


class PatchTeamMember(PostTeamMember):
    """Request body for ``PATCH`` on ticket team-member endpoints.

    Inherits all fields from :class:`PostTeamMember`.
    """


class DeleteTeamMember(GlpiModel):
    """Placeholder body for ``DELETE`` on ticket team-member endpoints.

    The contract advertises the role, itemtype and user identifiers as
    path parameters and exposes no body or query parameters; this empty
    model is kept for parity with the rest of the ``api_schema`` package.
    """


__all__ = [
    "DeleteTeamMember",
    "GetTeamMember",
    "PatchTeamMember",
    "PostTeamMember",
]
