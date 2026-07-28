"""Unit tests for :mod:`glpi_python_client._sync.clients.commons._payloads`."""

from __future__ import annotations

from glpi_python_client._sync.clients.commons._payloads import (
    model_from_payload,
    model_to_payload,
)
from glpi_python_client.models.api_schema.administration._user import (
    GetUser,
    PostUser,
)


def test_model_to_payload_excludes_none_and_extra_payload_meta() -> None:
    """The helper drops ``None`` fields and the ``extra_payload`` meta key."""

    user = PostUser(username="alice", realname=None)
    body = model_to_payload(user)
    assert body == {"username": "alice"}


def test_model_to_payload_merges_user_extra_payload() -> None:
    """User-provided ``extra_payload`` keys are merged into the request body."""

    user = PostUser(username="alice", extra_payload={"comment": "hi"})
    body = model_to_payload(user)
    assert body["comment"] == "hi"


def test_model_from_payload_validates_response_data() -> None:
    """``model_from_payload`` is a thin wrapper around ``model_validate``."""

    parsed = model_from_payload(GetUser, {"id": 7, "username": "alice"})
    assert parsed.id == 7
    assert parsed.username == "alice"


def test_capture_extra_keys_passes_non_dict_input_through() -> None:
    """The base validator returns non-mapping inputs untouched."""

    # ``model_validate`` may receive non-mapping input (e.g. another model
    # instance) and the ``_capture_extra_keys`` validator must short-circuit
    # without trying to mutate it. Using an existing instance exercises the
    # ``return data`` early-exit branch in ``_base.GlpiModel``.
    original = PostUser(username="bob")
    revalidated = PostUser.model_validate(original)
    assert revalidated.username == "bob"


def test_capture_extra_keys_merges_with_existing_extra_payload_dict() -> None:
    """Caller-provided ``extra_payload`` wins over keys captured from the body."""

    user = PostUser.model_validate(
        {
            "username": "alice",
            "stranger": "captured",
            "extra_payload": {"caller_wins": True, "stranger": "explicit"},
        }
    )
    assert user.extra_payload == {
        "stranger": "explicit",
        "caller_wins": True,
    }
