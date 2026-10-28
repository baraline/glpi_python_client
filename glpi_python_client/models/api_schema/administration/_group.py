"""GLPI ``Group`` schemas for the ``/Administration/Group`` endpoints.

The field layout mirrors ``components.schemas.Group`` from the GLPI OpenAPI
contract. Read-only contract fields are not declared on the request models;
a caller that supplies one anyway sends it through ``extra_payload`` and the
server decides.
"""

from __future__ import annotations

from datetime import datetime

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef


class GetGroup(GlpiModel):
    """Response shape returned by ``GET /Administration/Group`` endpoints.

    Mirrors ``components.schemas.Group``. All fields are optional because
    the contract does not advertise a ``required`` array.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier (``readOnly``).
    name : str | None, optional
        Name of the group.
    comment : str | None, optional
        Free-form comment.
    completename : str | None, optional
        Full hierarchical path of the group (``readOnly``).
    parent : IdNameRef | None, optional
        Parent group in the hierarchy.
    level : int | None, optional
        Depth of the group in the hierarchy tree (``readOnly``).
    entity : IdNameRef | None, optional
        Entity the group belongs to.
    code : str | None, optional
        Group code (at most 255 characters).
    ldap_field : str | None, optional
        LDAP user attribute that may contain this group (memberof).
    ldap_value : str | None, optional
        LDAP attribute value to match for membership, usually the DN.
    ldap_group_dn : str | None, optional
        DN of the group in LDAP; only populated in certain cases.
    maybe_requester : bool | None, optional
        Can be a requester.
    maybe_observer : bool | None, optional
        Can be an observer.
    maybe_assigned : bool | None, optional
        Can be assigned (to tickets).
    maybe_assigned_task : bool | None, optional
        Can be assigned to tasks.
    maybe_notified : bool | None, optional
        Can be notified.
    may_contain_items : bool | None, optional
        Can contain items.
    may_contain_users : bool | None, optional
        Can contain users.
    maybe_manager : bool | None, optional
        Can be manager.
    recursive_membership : bool | None, optional
        Whether users of this group are implied members of all child
        groups. Unrelated to entity recursion.
    mfa_enforced : bool | None, optional
        Whether two-factor authentication is enforced for members.
    date_creation : datetime | None, optional
        Creation timestamp.
    date_mod : datetime | None, optional
        Last modification timestamp.
    """

    id: int | None = None
    name: str | None = None
    comment: str | None = None
    completename: str | None = None
    parent: IdNameRef | None = None
    level: int | None = None
    entity: IdNameRef | None = None
    code: str | None = None
    ldap_field: str | None = None
    ldap_value: str | None = None
    ldap_group_dn: str | None = None
    maybe_requester: bool | None = None
    maybe_observer: bool | None = None
    maybe_assigned: bool | None = None
    maybe_assigned_task: bool | None = None
    maybe_notified: bool | None = None
    may_contain_items: bool | None = None
    may_contain_users: bool | None = None
    maybe_manager: bool | None = None
    recursive_membership: bool | None = None
    mfa_enforced: bool | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None


class PostGroup(GlpiModel):
    """Request body for ``POST /Administration/Group``.

    Read-only contract fields (``id``, ``completename``, ``level``) and the
    server-set timestamps are not declared; see :class:`GetGroup` for the
    meaning of each field.
    """

    name: str | None = None
    comment: str | None = None
    parent: IdNameRef | None = None
    entity: IdNameRef | None = None
    code: str | None = None
    ldap_field: str | None = None
    ldap_value: str | None = None
    ldap_group_dn: str | None = None
    maybe_requester: bool | None = None
    maybe_observer: bool | None = None
    maybe_assigned: bool | None = None
    maybe_assigned_task: bool | None = None
    maybe_notified: bool | None = None
    may_contain_items: bool | None = None
    may_contain_users: bool | None = None
    maybe_manager: bool | None = None
    recursive_membership: bool | None = None
    mfa_enforced: bool | None = None


class PatchGroup(PostGroup):
    """Request body for ``PATCH /Administration/Group/{id}``.

    The contract uses the same ``Group`` schema for create and
    partial-update bodies; ``PatchGroup`` is kept distinct so client
    mixins can express the intent of the operation explicitly.
    """


class DeleteGroup(GlpiModel):
    """Query parameters for ``DELETE /Administration/Group/{id}``.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the group instead of moving the
        record to the GLPI trash. When ``False`` or :data:`None`, the
        server applies its default soft-delete behaviour.
    """

    force: bool | None = None


__all__ = ["DeleteGroup", "GetGroup", "PatchGroup", "PostGroup"]
