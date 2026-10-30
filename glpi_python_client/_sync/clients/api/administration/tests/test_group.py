"""Unit tests for the ``Administration/Group`` endpoint mixin."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import GlpiProtocolError, PatchGroup, PostGroup
from glpi_python_client._sync._testing import (
    FailingTransportRecorder,
    TransportRecorder,
)
from glpi_python_client.models.api_schema._common import IdNameRef


def test_search_groups_sends_the_filter(client: Any) -> None:
    """``search_groups`` forwards filter, limit and start; header kept."""

    rec = TransportRecorder(get_payload=[{"id": 7, "name": "Team A"}])
    rec.install(client)
    groups = client.search_groups("name==x", limit=10, start=5)
    assert groups[0].id == 7
    call = rec.calls[0]
    assert call["endpoint"] == "Administration/Group"
    assert call["params"] == {"limit": 10, "start": 5, "filter": "name==x"}
    assert call["skip_entity"] is False


def test_search_groups_forwards_skip_entity(client: Any) -> None:
    """``skip_entity=True`` reaches the transport."""

    rec = TransportRecorder(get_payload=[])
    rec.install(client)
    client.search_groups("name==x", skip_entity=True)
    assert rec.calls[0]["skip_entity"] is True


def test_get_group_targets_group_endpoint(client: Any) -> None:
    """``get_group`` reads the per-id endpoint."""

    rec = TransportRecorder(get_payload={"id": 7, "name": "Team A"})
    rec.install(client)
    group = client.get_group(7)
    assert group.id == 7
    assert rec.calls[0]["endpoint"] == "Administration/Group/7"
    assert rec.calls[0]["skip_entity"] is False


def test_create_group_posts_the_body_and_returns_the_id(client: Any) -> None:
    """``create_group`` posts entity and ``maybe_assigned`` and returns the id."""

    rec = TransportRecorder(post_payload={"id": 42})
    rec.install(client)
    group_id = client.create_group(
        PostGroup(name="Team A", entity=IdNameRef(id=492), maybe_assigned=True)
    )
    assert group_id == 42
    call = rec.calls[0]
    assert call["endpoint"] == "Administration/Group"
    assert call["json"]["entity"]["id"] == 492
    assert call["json"]["maybe_assigned"] is True
    assert call["json"]["name"] == "Team A"
    assert call["skip_entity"] is False


def test_update_group_sends_patch(client: Any) -> None:
    """``update_group`` patches the per-id endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    client.update_group(7, PatchGroup(name="renamed"))
    assert rec.calls[0]["endpoint"] == "Administration/Group/7"
    assert rec.calls[0]["json"] == {"name": "renamed"}


def test_delete_group_supports_force_flag(client: Any) -> None:
    """``delete_group(force=True)`` ships the force flag."""

    rec = TransportRecorder()
    rec.install(client)
    client.delete_group(7, force=True)
    call = rec.calls[0]
    assert call["endpoint"] == "Administration/Group/7"
    assert call["json"] == {"force": True}


@pytest.mark.parametrize("call", [lambda c: c.get_group(1)])
def test_get_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every read helper raises on a non-success status."""

    FailingTransportRecorder(404).install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize("call", [lambda c: c.create_group(PostGroup(name="x"))])
def test_create_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every create helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize("call", [lambda c: c.update_group(1, PatchGroup(name="x"))])
def test_update_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every update helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize("call", [lambda c: c.delete_group(1, force=True)])
def test_delete_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every delete helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        call(client)


def test_iter_search_groups_pages_until_short(client: Any) -> None:
    """Iteration stops after the first short batch and forwards skip_entity."""

    responses = [
        [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}],
        [{"id": 3, "name": "c"}],
    ]
    seen: list[tuple[int, bool]] = []

    def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        skip_entity: bool = False,
    ) -> list[Any]:
        seen.append((start, skip_entity))
        return responses[len(seen) - 1]

    client.search_groups = fake_search  # type: ignore[method-assign]
    batches = [
        b for b in client.iter_search_groups("", batch_size=2, skip_entity=True)
    ]
    assert seen == [(0, True), (2, True)]
    assert sum(len(b) for b in batches) == 3


class _FakeV1:
    """Stand-in for the v1 session that records ``request_json`` calls."""

    def __init__(self, *responses: object) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, object] | None = None,
        json_body: dict[str, object] | None = None,
        success_statuses: tuple[int, ...] = (200, 201, 204, 206),
        failure_message: str | None = None,
    ) -> object:
        self.calls.append(
            {
                "method": method,
                "path": path,
                "params": params,
                "json_body": json_body,
                "failure_message": failure_message,
            }
        )
        return self.responses.pop(0)

    def close(self) -> None:
        """No-op; the real session is closed with the client."""


def test_set_group_recursive_puts_the_flag_through_v1(client: Any) -> None:
    """``set_group_recursive`` sends ``is_recursive: 1`` to the v1 Group route."""

    fake = _FakeV1([{"7": True, "message": ""}])
    client._v1 = fake
    client.set_group_recursive(7)
    call = fake.calls[0]
    assert call["method"] == "PUT"
    assert call["path"] == "Group/7"
    assert call["json_body"] == {"input": {"id": 7, "is_recursive": 1}}


def test_set_group_recursive_false_sends_zero(client: Any) -> None:
    """``recursive=False`` sends ``is_recursive: 0``."""

    fake = _FakeV1([{"7": True, "message": ""}])
    client._v1 = fake
    client.set_group_recursive("7", recursive=False)
    assert fake.calls[0]["json_body"] == {"input": {"id": 7, "is_recursive": 0}}


def test_set_group_recursive_raises_on_a_refused_answer(client: Any) -> None:
    """A ``false`` answer raises with the server message, never passes."""

    client._v1 = _FakeV1([{"7": False, "message": "Right missing"}])
    with pytest.raises(GlpiProtocolError, match="Right missing"):
        client.set_group_recursive(7)


def test_set_group_recursive_requires_the_v1_session(client: Any) -> None:
    """Without a v1 session the usual configuration error is raised."""

    with pytest.raises(RuntimeError, match="group recursion"):
        client.set_group_recursive(7)
