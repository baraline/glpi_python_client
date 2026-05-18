"""GLPI ``User`` schemas for the ``/Administration/User`` endpoints.

The field layout mirrors ``components.schemas.User`` from the GLPI OpenAPI
contract. Read-only contract fields are excluded from the request models.
Sensitive credential fields (``password``, ``password2``) are wrapped in
:class:`pydantic.SecretStr` so the values are masked in logs, ``repr``
output and tracebacks, while a dedicated field serializer unmasks them
when the model is dumped into an outgoing request body.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import SecretStr, field_serializer

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef
from glpi_python_client.models.api_schema.enums import GlpiUserAuthType


class _EmailAddress(GlpiModel):
    """One e-mail entry of the ``User.emails`` array.

    Mirrors the inline ``EmailAddress`` object embedded in
    ``components.schemas.User.emails`` from the GLPI OpenAPI contract.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier (contract field ``id`` — ``ID``).
    email : str | None, optional
        E-mail address value (contract field ``email`` — ``Email address``).
    is_default : bool | None, optional
        Whether this address is the user's default e-mail (contract field
        ``is_default`` — ``Is default``).
    is_dynamic : bool | None, optional
        Whether this address was provisioned dynamically by GLPI, for
        example through an LDAP synchronisation (contract field
        ``is_dynamic`` — ``Is dynamic``).
    """

    id: int | None = None
    email: str | None = None
    is_default: bool | None = None
    is_dynamic: bool | None = None


class GetUser(GlpiModel):
    """Response shape returned by ``GET /Administration/User`` endpoints.

    Mirrors ``components.schemas.User`` (GLPI description: ``Utilisateur``).
    All fields are optional because the contract does not advertise a
    ``required`` array; absent or ``null`` values from the server are
    surfaced as :data:`None`. Credential fields are marked ``writeOnly`` in
    the contract and are therefore never returned by GET endpoints, so they
    are absent from this model.

    Parameters
    ----------
    id : int | None, optional
        Native GLPI identifier (contract field ``id`` — ``ID``,
        ``readOnly``).
    username : str | None, optional
        Login name of the user (contract field ``username`` — ``Username``).
    realname : str | None, optional
        Family name (contract field ``realname`` — ``Real name``).
    firstname : str | None, optional
        Given name (contract field ``firstname`` — ``First name``).
    phone : str | None, optional
        Primary phone number (contract field ``phone`` — ``Phone number``).
    phone2 : str | None, optional
        Secondary phone number (contract field ``phone2`` —
        ``Phone number 2``).
    mobile : str | None, optional
        Mobile phone number (contract field ``mobile`` —
        ``Mobile phone number``).
    emails : list[_EmailAddress] | None, optional
        Collection of e-mail addresses attached to the user (contract field
        ``emails`` — ``Email addresses``).
    comment : str | None, optional
        Free-form comment associated with the user (contract field
        ``comment`` — ``Comment``).
    is_active : bool | None, optional
        Whether the account is currently active (contract field
        ``is_active`` — ``Is active``).
    is_deleted : bool | None, optional
        Whether the account has been moved to the trash (contract field
        ``is_deleted`` — ``Is deleted``).
    picture : str | None, optional
        Path or identifier of the avatar picture (contract field
        ``picture``, ``readOnly``).
    date_password_change : datetime | None, optional
        Timestamp of the last password change (contract field
        ``date_password_change`` — ``Date of last password change``,
        ``readOnly``).
    location : IdNameRef | None, optional
        Reference to the user's default location (contract field
        ``location`` — embedded ``Location`` object).
    authtype : GlpiUserAuthType | None, optional
        Authentication backend used for this account (contract field
        ``authtype``). Numeric enumeration: ``1`` GLPI database, ``2``
        Email, ``3`` LDAP, ``4`` External, ``5`` CAS, ``6`` X.509
        Certificate.
    last_login : datetime | None, optional
        Timestamp of the user's last successful login (contract field
        ``last_login``).
    default_profile : IdNameRef | None, optional
        Default profile assumed by the user at login (contract field
        ``default_profile`` — ``Default profile``).
    default_entity : IdNameRef | None, optional
        Default entity scope assumed by the user at login (contract field
        ``default_entity`` — ``Default entity``).
    date_creation : datetime | None, optional
        Creation timestamp of the user record (contract field
        ``date_creation``).
    date_mod : datetime | None, optional
        Last modification timestamp of the user record (contract field
        ``date_mod``).
    date_sync : datetime | None, optional
        Last synchronisation timestamp with the external directory
        (contract field ``date_sync``, ``readOnly``).
    title : IdNameRef | None, optional
        Reference to the user's ``UserTitle`` (contract field ``title``;
        no contract description).
    category : IdNameRef | None, optional
        Reference to the user's ``UserCategory`` (contract field
        ``category``).
    registration_number : str | None, optional
        Free-form registration/employee number (contract field
        ``registration_number``).
    begin_date : datetime | None, optional
        Beginning of the validity window for the account (contract field
        ``begin_date`` — ``Valid since``).
    end_date : datetime | None, optional
        End of the validity window for the account (contract field
        ``end_date`` — ``Valid until``).
    nickname : str | None, optional
        Display nickname for the user (contract field ``nickname``,
        ``maxLength=50``).
    substitution_start_date : datetime | None, optional
        Start of the period during which this user is acting as a
        substitute (contract field ``substitution_start_date``).
    substitution_end_date : datetime | None, optional
        End of the period during which this user is acting as a substitute
        (contract field ``substitution_end_date``).
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

    Mirrors ``components.schemas.User`` for create operations. Read-only
    contract fields (``id``, ``picture``, ``date_password_change``,
    ``date_sync``) are intentionally excluded because the server rejects
    them on input. The contract marks ``password`` and ``password2`` as
    ``writeOnly``: they are accepted on create/update but never returned by
    GET endpoints.

    The two credential fields are typed as :class:`pydantic.SecretStr` so
    that the cleartext values do not leak through ``repr``, log records,
    structured tracebacks or interactive debuggers. Their serializer
    unmasks the value via :meth:`SecretStr.get_secret_value` when the model
    is dumped into the outgoing JSON request body, so the API still
    receives the plain credential as it expects.

    Parameters
    ----------
    username : str | None, optional
        Login name of the user (contract field ``username`` — ``Username``).
    realname : str | None, optional
        Family name (contract field ``realname`` — ``Real name``).
    firstname : str | None, optional
        Given name (contract field ``firstname`` — ``First name``).
    phone : str | None, optional
        Primary phone number (contract field ``phone`` — ``Phone number``).
    phone2 : str | None, optional
        Secondary phone number (contract field ``phone2`` —
        ``Phone number 2``).
    mobile : str | None, optional
        Mobile phone number (contract field ``mobile`` —
        ``Mobile phone number``).
    emails : list[_EmailAddress] | None, optional
        Collection of e-mail addresses attached to the user (contract field
        ``emails`` — ``Email addresses``).
    comment : str | None, optional
        Free-form comment associated with the user (contract field
        ``comment`` — ``Comment``).
    is_active : bool | None, optional
        Whether the account should be created in the active state
        (contract field ``is_active`` — ``Is active``).
    is_deleted : bool | None, optional
        Whether the account should be created in the trashed state
        (contract field ``is_deleted`` — ``Is deleted``).
    password : SecretStr | None, optional
        Cleartext password to assign to the account (contract field
        ``password`` — ``Password``, ``format=password``, ``writeOnly``).
        Wrapped in :class:`SecretStr`; the value is unmasked only when the
        request body is serialised.
    password2 : SecretStr | None, optional
        Confirmation of :attr:`password`; the GLPI server validates that
        both fields match before persisting the account (contract field
        ``password2`` — ``Password confirmation``, ``format=password``,
        ``writeOnly``). Wrapped in :class:`SecretStr`; unmasked only on
        serialisation.
    location : IdNameRef | None, optional
        Reference to the user's default location (contract field
        ``location`` — embedded ``Location`` object).
    authtype : GlpiUserAuthType | None, optional
        Authentication backend used for this account (contract field
        ``authtype``). Numeric enumeration: ``1`` GLPI database, ``2``
        Email, ``3`` LDAP, ``4`` External, ``5`` CAS, ``6`` X.509
        Certificate.
    last_login : datetime | None, optional
        Timestamp of the user's last successful login (contract field
        ``last_login``).
    default_profile : IdNameRef | None, optional
        Default profile assumed by the user at login (contract field
        ``default_profile`` — ``Default profile``).
    default_entity : IdNameRef | None, optional
        Default entity scope assumed by the user at login (contract field
        ``default_entity`` — ``Default entity``).
    date_creation : datetime | None, optional
        Creation timestamp to override on the user record (contract field
        ``date_creation``).
    date_mod : datetime | None, optional
        Last modification timestamp to override on the user record
        (contract field ``date_mod``).
    title : IdNameRef | None, optional
        Reference to the user's ``UserTitle`` (contract field ``title``;
        no contract description).
    category : IdNameRef | None, optional
        Reference to the user's ``UserCategory`` (contract field
        ``category``).
    registration_number : str | None, optional
        Free-form registration/employee number (contract field
        ``registration_number``).
    begin_date : datetime | None, optional
        Beginning of the validity window for the account (contract field
        ``begin_date`` — ``Valid since``).
    end_date : datetime | None, optional
        End of the validity window for the account (contract field
        ``end_date`` — ``Valid until``).
    nickname : str | None, optional
        Display nickname for the user (contract field ``nickname``,
        ``maxLength=50``).
    substitution_start_date : datetime | None, optional
        Start of the period during which this user is acting as a
        substitute (contract field ``substitution_start_date``).
    substitution_end_date : datetime | None, optional
        End of the period during which this user is acting as a substitute
        (contract field ``substitution_end_date``).
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
    password: SecretStr | None = None
    password2: SecretStr | None = None
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

    @field_serializer("password", "password2", when_used="always")
    def _dump_secret(self, value: SecretStr | None) -> str | None:
        """Unmask :class:`SecretStr` credentials when serialising the body.

        Pydantic's default :class:`SecretStr` serializer emits the masked
        placeholder (``'**********'``) for both ``mode='python'`` and
        ``mode='json'``. The GLPI API expects the actual cleartext, so the
        serializer returns :meth:`SecretStr.get_secret_value` for non-null
        values and propagates :data:`None` unchanged so that
        ``model_dump(exclude_none=True)`` keeps stripping the field when
        the caller did not set a password.
        """

        if value is None:
            return None
        return value.get_secret_value()


class PatchUser(PostUser):
    """Request body for ``PATCH /Administration/User/{id}``.

    The contract uses the same ``User`` schema for create and partial-update
    bodies; ``PatchUser`` is kept distinct so client mixins can express the
    intent of the operation explicitly. All fields, including the
    ``SecretStr``-wrapped ``password`` / ``password2`` pair inherited from
    :class:`PostUser`, behave exactly as on create.
    """


class DeleteUser(GlpiModel):
    """Query parameters for ``DELETE /Administration/User/{id}``.

    Parameters
    ----------
    force : bool | None, optional
        When ``True``, permanently delete the user instead of moving the
        record to the GLPI trash. When ``False`` or :data:`None`, the
        server applies its default soft-delete behaviour and the user can
        still be restored.
    """

    force: bool | None = None


__all__ = ["DeleteUser", "GetUser", "PatchUser", "PostUser"]
