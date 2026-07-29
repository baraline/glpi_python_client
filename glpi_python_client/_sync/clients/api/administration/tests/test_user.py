"""Unit tests for the ``Administration/User`` endpoint mixin.

The tests cover search, fetch, create, update, delete, and page-by-page
iteration for GLPI users, using the shared transport recorders to stub
the four transport helpers without any HTTP plumbing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import PatchUser, PostUser
from glpi_python_client._sync._testing import (
    FailingTransportRecorder,
    TransportRecorder,
)

# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def test_search_users_forwards_skip_entity(client: Any) -> None:
    """``search_users`` forwards the ``skip_entity`` flag."""

    rec = TransportRecorder(get_payload=[{"id": 1, "username": "alice"}])
    rec.install(client)
    users = client.search_users("username==alice", skip_entity=True)
    assert len(users) == 1
    assert rec.calls[0]["skip_entity"] is True
    assert rec.calls[0]["params"]["filter"] == "username==alice"


def test_get_user_targets_user_endpoint(client: Any) -> None:
    """``get_user`` hits the per-id endpoint."""

    rec = TransportRecorder(get_payload={"id": 5, "username": "alice"})
    rec.install(client)
    user = client.get_user(5)
    assert user.id == 5
    assert rec.calls[0]["endpoint"] == "Administration/User/5"


def test_update_user_sends_patch(client: Any) -> None:
    """``update_user`` issues PATCH against the user endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    client.update_user(5, PatchUser(firstname="Alice"))
    assert rec.calls[0]["method"] == "PATCH"
    assert rec.calls[0]["endpoint"] == "Administration/User/5"


def test_create_user_serialises_post_body(client: Any) -> None:
    """``create_user`` serialises the ``PostUser`` model into the POST body."""

    rec = TransportRecorder()
    rec.install(client)
    user_id = client.create_user(PostUser(username="alice"))
    assert user_id == 999
    assert rec.calls == [
        {
            "method": "POST",
            "endpoint": "Administration/User",
            "json": {"username": "alice"},
            "skip_entity": False,
        }
    ]


def test_delete_user_supports_force_flag(client: Any) -> None:
    """``delete_user`` forwards the ``force`` flag inside the JSON body."""

    rec = TransportRecorder()
    rec.install(client)
    client.delete_user(5, force=True)
    call = rec.calls[0]
    assert call["method"] == "DELETE"
    assert call["endpoint"] == "Administration/User/5"
    assert call["json"] == {"force": True}


# ---------------------------------------------------------------------------
# Generic error handling (this mixin's share of the shared failure suites)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_user(1),
    ],
)
def test_get_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every read helper raises on a non-success status."""

    FailingTransportRecorder(404).install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.update_user(1, PatchUser(firstname="x")),
    ],
)
def test_update_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every update helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.delete_user(1, force=True),
    ],
)
def test_delete_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every delete helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        call(client)


# ---------------------------------------------------------------------------
# iter_search_users
# ---------------------------------------------------------------------------


def test_iter_search_users_single_page(client: Any) -> None:
    """A response shorter than batch_size yields one batch then stops."""

    call_count = 0

    def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        skip_entity: bool = False,
    ) -> list[Any]:
        nonlocal call_count
        call_count += 1
        return [{"id": 1, "username": "alice"}]

    client.search_users = fake_search  # type: ignore[method-assign]
    batches = [
        b for b in client.iter_search_users("username==alice", batch_size=50)
    ]
    assert call_count == 1
    assert len(batches) == 1


def test_iter_search_users_multi_page_stops_on_short_batch(
    client: Any,
) -> None:
    """Iteration stops after the first short user batch."""

    responses = [
        [{"id": 1, "username": "alice"}, {"id": 2, "username": "bob"}],
        [{"id": 3, "username": "carol"}],
    ]
    call_count = 0

    def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        skip_entity: bool = False,
    ) -> list[Any]:
        nonlocal call_count
        result = responses[min(call_count, len(responses) - 1)]
        call_count += 1
        return result

    client.search_users = fake_search  # type: ignore[method-assign]
    batches = [batch for batch in client.iter_search_users("", batch_size=2)]
    assert call_count == 2
    assert sum(len(b) for b in batches) == 3
