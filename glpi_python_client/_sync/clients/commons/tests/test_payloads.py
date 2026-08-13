"""Unit tests for :mod:`glpi_python_client._sync.clients.commons._payloads`."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from glpi_python_client._sync.clients.commons._payloads import (
    model_from_payload,
    model_to_payload,
)
from glpi_python_client.models.api_schema.administration._user import (
    GetUser,
    PostUser,
)
from glpi_python_client.models.api_schema.assistance.timeline._task import (
    PostTicketTask,
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


def test_model_to_payload_body_is_json_encodable() -> None:
    """Every value in the body survives the JSON encoder httpx will use.

    ``_execute_request`` hands the mapping straight to ``httpx`` as ``json=``,
    whose encoder is ``json.dumps``. A body holding a live ``datetime`` object
    raises ``TypeError`` there -- after the model validated, and outside any
    transport stub -- so the assertion has to be encodability, not shape.
    """

    body = model_to_payload(PostTicketTask(planned_begin=datetime(2024, 1, 1, 12, 0)))

    assert json.dumps(body)


def test_model_to_payload_renders_naive_datetime_without_offset() -> None:
    """A naive datetime reaches GLPI as the bare timestamp it was given."""

    body = model_to_payload(PostTicketTask(planned_begin=datetime(2024, 1, 1, 12, 0)))

    assert body["planned_begin"] == "2024-01-01T12:00:00"


def test_model_to_payload_rewrites_an_aware_datetime_onto_the_server_clock() -> None:
    """An aware datetime is converted to server-local time and sent bare.

    GLPI 11 ignores the offset it is sent -- measured, three spellings of one
    moment all stored the same wall clock -- so writing ``12:00Z`` to a
    ``+01:00`` instance stores 12:00 there and loses an hour silently. The
    offset has to be spent on the conversion instead of written out.
    """

    aware = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    body = model_to_payload(
        PostTicketTask(planned_begin=aware),
        server_timezone=timezone(timedelta(hours=1)),
    )

    assert body["planned_begin"] == "2024-01-01T13:00:00"


def test_model_to_payload_leaves_an_aware_datetime_alone_without_a_timezone() -> None:
    """Outside the client there is no server clock to convert onto."""

    aware = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    body = model_to_payload(PostTicketTask(planned_begin=aware))

    assert body["planned_begin"] == "2024-01-01T12:00:00Z"
