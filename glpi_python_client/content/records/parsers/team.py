"""GLPI team-member record parsing helpers.

This module turns raw team-association payloads into typed team-member models
used by the ticket team helpers.
"""

from __future__ import annotations

from typing import Any

from glpi_python_client.content.records.core.scalars import _first_int, _optional_text
from glpi_python_client.models import GlpiTeamMember


def _glpi_team_member_record(raw_member: dict[str, Any]) -> GlpiTeamMember | None:
    """Build a ``GlpiTeamMember`` from one raw association payload.

    Incomplete associations are skipped by returning ``None`` so list parsing
    can continue without failing the whole team-member batch.
    """

    member_type = _resolve_glpi_member_type(raw_member)
    member_id = _first_int(
        raw_member.get("id"), raw_member.get("items_id"), raw_member.get("users_id")
    )
    role = _optional_text(raw_member.get("role"))
    if member_type is None or member_id is None or role is None:
        return None
    return GlpiTeamMember(
        member_type=member_type,
        member_id=member_id,
        role=role,
        name=_optional_text(raw_member.get("display_name"))
        or _optional_text(raw_member.get("name")),
        display_name=_optional_text(raw_member.get("display_name"))
        or _optional_text(raw_member.get("name")),
    )


def _resolve_glpi_member_type(member: dict[str, Any]) -> str | None:
    """Resolve the GLPI team-member type from explicit fields or links.

    GLPI may provide the member type directly or only imply it through the
    linked form URL, so both sources are considered.
    """

    member_type = member.get("itemtype") or member.get("type")
    if isinstance(member_type, str) and member_type:
        return member_type
    href = member.get("href")
    if not isinstance(href, str) or not href:
        return None
    lowered = href.casefold()
    if "/group.form.php" in lowered:
        return "Group"
    if "/user.form.php" in lowered:
        return "User"
    return None
