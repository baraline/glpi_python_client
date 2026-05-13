"""Typed GLPI team-member model.

The team-member model is used by the ticket team helpers for both parsed team
associations and outgoing membership mutations.
"""

from __future__ import annotations

from glpi_python_client.models._base import GlpiModel


class GlpiTeamMember(GlpiModel):
    """GLPI team-member rich object.

    Parameters
    ----------
    member_type : str
        GLPI member type such as ``"User"`` or ``"Group"``.
    member_id : int
        Native GLPI member identifier when known.
    role : str
        Team role carried by the member.
    name : str | None, optional
        Optional member name.
    display_name : str | None, optional
        Optional display name.
    """

    member_type: str
    member_id: int
    role: str
    name: str | None = None
    display_name: str | None = None
