"""Smoke tests for the administration api_schema models.

The tests confirm that the per-verb Pydantic models honour the GLPI
contract field shapes for ``User`` and ``Entity`` and that read-only
contract fields are excluded from the create and patch request models.
"""

from __future__ import annotations

from pydantic import SecretStr

from glpi_python_client.models.api_schema.administration import (
    DeleteEntity,
    DeleteUser,
    GetEntity,
    GetUser,
    PatchEntity,
    PatchUser,
    PostEntity,
    PostUser,
)
from glpi_python_client.models.api_schema.enums import GlpiUserAuthType


def test_get_user_validates_full_contract_payload() -> None:
    """``GetUser`` accepts every contract field of the ``User`` schema."""

    payload = {
        "id": 42,
        "username": "alice",
        "realname": "Doe",
        "firstname": "Alice",
        "phone": "0102",
        "phone2": "0304",
        "mobile": "0506",
        "emails": [
            {"id": 1, "email": "a@x", "is_default": True, "is_dynamic": False},
        ],
        "comment": "hello",
        "is_active": True,
        "is_deleted": False,
        "picture": "url",
        "date_password_change": "2024-01-02T03:04:05",
        "location": {"id": 7, "name": "HQ"},
        "authtype": 2,
        "default_entity": {"id": 0, "name": "root"},
    }
    user = GetUser.model_validate(payload)
    assert user.id == 42
    assert user.authtype is GlpiUserAuthType.LDAP
    assert user.emails is not None
    assert user.emails[0].email == "a@x"


def test_post_user_excludes_read_only_fields() -> None:
    """Read-only fields land in ``extra_payload`` so the GLPI server validates them."""

    user = PostUser.model_validate({"id": 1, "username": "alice"})
    assert user.username == "alice"
    assert user.extra_payload == {"id": 1}


def test_patch_user_shares_post_shape() -> None:
    """``PatchUser`` accepts the same writable fields as ``PostUser``."""

    payload = {"username": "bob", "comment": "updated"}
    assert (
        PatchUser.model_validate(payload).model_dump(
            exclude_none=True, exclude={"extra_payload"}
        )
        == payload
    )


def test_delete_user_force_query_param() -> None:
    """``DeleteUser`` exposes the optional ``force`` query parameter."""

    assert DeleteUser().force is None
    assert DeleteUser(force=True).force is True


def test_get_entity_full_payload() -> None:
    """``GetEntity`` accepts every contract field of the ``Entity`` schema."""

    payload = {
        "id": 5,
        "name": "Org",
        "comment": "root",
        "completename": "Org",
        "parent": {"id": 0, "name": "root"},
        "level": 1,
    }
    entity = GetEntity.model_validate(payload)
    assert entity.id == 5
    assert entity.parent is not None
    assert entity.parent.id == 0


def test_post_entity_rejects_read_only_fields() -> None:
    """Read-only fields are routed into ``extra_payload`` for server validation."""

    for forbidden in ("id", "completename", "level"):
        entity = PostEntity.model_validate({"name": "Org", forbidden: "x"})
        assert entity.extra_payload == {forbidden: "x"}


def test_patch_entity_accepts_subset() -> None:
    """``PatchEntity`` accepts a partial body without errors."""

    PatchEntity.model_validate({"comment": "changed"})


def test_delete_entity_default() -> None:
    """``DeleteEntity`` has an optional ``force`` flag."""

    assert DeleteEntity().force is None


def test_post_user_secret_serializer_unmasks_password() -> None:
    """``_dump_secret`` returns plaintext when a non-None ``SecretStr`` is set."""

    user = PostUser(
        username="alice",
        password=SecretStr("s3cr3t"),
        password2=SecretStr("s3cr3t"),
    )
    payload = user.model_dump(exclude_none=True, exclude={"extra_payload"})
    assert payload["password"] == "s3cr3t"
    assert payload["password2"] == "s3cr3t"
    # The repr must not expose the value.
    assert "s3cr3t" not in repr(user)


def test_post_user_secret_serializer_none_propagates() -> None:
    """``_dump_secret`` returns ``None`` when the credential field is ``None``.

    ``model_dump`` is called without ``exclude_none`` so the serializer is
    invoked with a ``None`` value rather than being skipped by Pydantic's
    optimisation path.
    """

    user = PostUser(username="bob")
    payload = user.model_dump(exclude={"extra_payload"})
    assert payload.get("password") is None
    assert payload.get("password2") is None
