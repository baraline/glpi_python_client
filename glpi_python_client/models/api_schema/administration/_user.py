"""GLPI ``User`` schemas for the ``/Administration/User`` endpoints.

The field layout mirrors ``components.schemas.User`` from the GLPI OpenAPI
contract. Read-only contract fields are excluded from the request models.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef
from glpi_python_client.models.api_schema.enums import GlpiUserAuthType


class _EmailAddress(GlpiModel):
    """One e-mail entry of the ``User.emails`` array.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI e-mail identifier.
    email : str | None, optional
        E-mail address value.
    is_default : bool | None, optional
        Whether the e-mail is the default address.
    is_dynamic : bool | None, optional
        Whether the e-mail is provisioned dynamically by GLPI.
    """

    id: int | None = None
    email: str | None = None
    is_default: bool | None = None
    is_dynamic: bool | None = None


class GetUser(GlpiModel):
    """Response shape returned by ``GET /Administration/User`` endpoints.

    Mirrors ``components.schemas.User``. All fields are optional because the
    contract does not advertise a ``required`` array.
    """

    id: int | None = None
    username: str | None = None
    realname: str | None = None
    firstname: str | None = None
    phone: str | None = None
    phone2: str | None = None
    mobile: str | None = None
    emails: list[_EmailAddress] | None = None
    comment: str | None = None
    is_active: bool | None = None
    is_deleted: bool | None = None
    picture: str | None = None
    date_password_change: datetime | None = None
    location: IdNameRef | None = None
    authtype: GlpiUserAuthType | None = None
    last_login: datetime | None = None
    default_profile: IdNameRef | None = None
    default_entity: IdNameRef | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    date_sync: datetime | None = None
    title: IdNameRef | None = None
    category: IdNameRef | None = None
    registration_number: str | None = None
    begin_date: datetime | None = None
    end_date: datetime | None = None
    nickname: str | None = None
    substitution_start_date: datetime | None = None
    substitution_end_date: datetime | None = None


class PostUser(GlpiModel):
    """Request body for ``POST /Administration/User``.

    Read-only contract fields (``id``, ``picture``, ``date_password_change``,
    ``date_sync``) are intentionally excluded.
    """

    username: str | None = None
    realname: str | None = None
    firstname: str | None = None
    phone: str | None = None
    phone2: str | None = None
    mobile: str | None = None
    emails: list[_EmailAddress] | None = None
    comment: str | None = None
    is_active: bool | None = None
    is_deleted: bool | None = None
    password: str | None = None
    password2: str | None = None
    location: IdNameRef | None = None
    authtype: GlpiUserAuthType | None = None
    last_login: datetime | None = None
    default_profile: IdNameRef | None = None
    default_entity: IdNameRef | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    title: IdNameRef | None = None
    category: IdNameRef | None = None
    registration_number: str | None = None
    begin_date: datetime | None = None
    end_date: datetime | None = None
    nickname: str | None = None
    substitution_start_date: datetime | None = None
    substitution_end_date: datetime | None = None


class PatchUser(PostUser):
    """Request body for ``PATCH /Administration/User/{id}``.

    The contract uses the same ``User`` schema for create and partial-update
    bodies; ``PatchUser`` is kept distinct so client mixins can express the
    intent of the operation explicitly.
    """


class DeleteUser(GlpiModel):
    """Query parameters for ``DELETE /Administration/User/{id}``.

    Parameters
    ----------
    force : bool | None, optional
        Permanently delete the user instead of moving it to the trash.
    """

    force: bool | None = None


__all__ = ["DeleteUser", "GetUser", "PatchUser", "PostUser"]
