"""GLPI directory record parsing helpers for users and locations.

This module converts raw user and location payloads from directory-style GLPI
endpoints into the package's typed models.
"""

from __future__ import annotations

from typing import Any

from glpi_python_client.content.records.core.references import _glpi_id_value
from glpi_python_client.content.records.core.scalars import (
    _optional_int,
    _optional_text,
)
from glpi_python_client.models import GlpiEntity, GlpiLocation, GlpiUser

_KNOWN_ENTITY_FIELDS = {
    "id",
    "name",
    "complete_name",
    "completename",
    "comment",
}


def _glpi_user_record(raw_user: dict[str, Any]) -> GlpiUser:
    """Build a ``GlpiUser`` from one raw user payload.

    The parser derives a display name from the available first name, real name,
    and username fields while preserving the default entity when present.
    """

    user_id = _optional_text(raw_user.get("id"))
    if user_id is None:
        raise ValueError("GLPI user payload did not include an ID")
    default_entity = raw_user.get("default_entity")
    firstname = _optional_text(raw_user.get("firstname"))
    realname = _optional_text(raw_user.get("realname")) or _optional_text(
        raw_user.get("name")
    )
    return GlpiUser(
        user_id=user_id,
        email=_optional_text(raw_user.get("email"))
        or _optional_text(raw_user.get("username")),
        firstname=firstname,
        realname=realname,
        name=" ".join(part for part in (firstname, realname) if part)
        or realname
        or firstname,
        entity_id=_optional_int(_glpi_id_value(default_entity) or default_entity),
    )


def _glpi_entity_record(raw_entity: dict[str, Any]) -> GlpiEntity:
    """Build a ``GlpiEntity`` from one raw entity payload.

    The parser normalizes the public identifier and full-name fields while
    preserving any unmodeled payload values in ``extra_payload``.
    """

    entity_id = _optional_text(raw_entity.get("id"))
    if entity_id is None:
        raise ValueError("GLPI entity payload did not include an ID")
    return GlpiEntity(
        entity_id=entity_id,
        name=_optional_text(raw_entity.get("name")),
        complete_name=_optional_text(raw_entity.get("complete_name"))
        or _optional_text(raw_entity.get("completename")),
        comment=_optional_text(raw_entity.get("comment")),
        extra_payload={
            key: value
            for key, value in raw_entity.items()
            if key not in _KNOWN_ENTITY_FIELDS
        },
    )


def _glpi_location_record(raw_location: dict[str, Any]) -> GlpiLocation:
    """Build a ``GlpiLocation`` from one raw location payload.

    The location parser requires both the identifier and name because those
    fields are necessary for the high-level location model.
    """

    location_id = _optional_text(raw_location.get("id"))
    name = _optional_text(raw_location.get("name"))
    if location_id is None or name is None:
        raise ValueError("GLPI location payload did not include id and name")
    return GlpiLocation(
        location_id=location_id,
        name=name,
        entity_id=_optional_int(_glpi_id_value(raw_location.get("entity"))),
    )
