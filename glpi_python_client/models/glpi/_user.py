"""Typed GLPI user model.

The user model is used for parsed directory records, embedded ticket users, and
outgoing user-creation payloads.
"""

from __future__ import annotations

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models._payload import (
    ApiPayloadMixin,
    drop_empty_payload_values,
)


class GlpiUser(ApiPayloadMixin, GlpiModel):
    """GLPI user rich object.

    Parameters
    ----------
    user_id : str | None, optional
        Native GLPI user identifier.
    email : str | None, optional
        User email address.
    firstname : str | None, optional
        First name.
    realname : str | None, optional
        Last name.
    name : str | None, optional
        Display name.
    entity_id : int | None, optional
        Owning GLPI entity.
    default_is_notifications_enabled : bool | None, optional
        Default GLPI user notification preference.
    """

    user_id: str | None = None
    email: str | None = None
    firstname: str | None = None
    realname: str | None = None
    name: str | None = None
    entity_id: int | None = None
    default_is_notifications_enabled: bool | None = None

    def _build_api_payload(self) -> dict[str, object]:
        """Return the raw GLPI user-create request body.

        Returns
        -------
        dict[str, object]
            Raw GLPI user-create request body.

        Raises
        ------
        ValueError
            Raised when neither a name nor an email is available.
        """

        username = _first_not_none(self.email, self.name, self.user_id)
        if username is None:
            raise ValueError("GLPI user creation requires at least a name or email")
        firstname = self.firstname
        realname = self.realname
        fallback_identity = _first_not_none(self.name, self.email, username)
        if firstname is None and realname is None:
            firstname = fallback_identity
            realname = ""
        else:
            firstname = firstname or ""
            realname = realname or ""
        payload: dict[str, object] = {
            "id": self.user_id,
            "username": username,
            "email": self.email,
            "realname": realname,
            "firstname": firstname,
            "name": self.name if self.name is not None else username,
        }
        if self.entity_id is not None:
            payload["default_entity"] = {"id": self.entity_id}
        if self.default_is_notifications_enabled is not None:
            payload["default_is_notifications_enabled"] = (
                self.default_is_notifications_enabled
            )
        return drop_empty_payload_values(payload)


def _first_not_none(*values: str | None) -> str | None:
    for value in values:
        if value is not None:
            return value
    return None
