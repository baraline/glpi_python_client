"""Async-client tests for the Fields plugin aggregation helpers.

These helpers call sibling *public* methods through ``self``. On
``AsyncGlpiClient`` those resolve to bridge-wrapped coroutines, so without
a hand-written async override they raise ``TypeError: 'coroutine' object
is not iterable``. See clients/tests/test_async_selfcall_guard.py.
"""

from __future__ import annotations

from typing import Any

import pytest

from glpi_python_client import AsyncGlpiClient
from glpi_python_client.testing.utils import make_async_client


class _FakeV1:
    """Stand-in for ``GLPIV1Session`` returning queued payloads."""

    def __init__(self, responses: list[object]) -> None:
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
        self.calls.append({"method": method, "path": path, "json_body": json_body})
        if not self.responses:
            raise AssertionError(f"Unexpected v1 call: {method} {path}")
        return self.responses.pop(0)


@pytest.fixture
def client() -> AsyncGlpiClient:
    """Return an async client with no HTTP plumbing wired up."""

    return make_async_client()


async def test_get_ticket_custom_fields_returns_values(
    client: AsyncGlpiClient,
) -> None:
    """The async helper must return data, not a dropped coroutine."""

    client._v1 = _FakeV1(  # type: ignore[assignment]
        [
            [{"id": 1, "name": "custom", "itemtypes": '["Ticket"]'}],
            [{"id": 5, "customfield": "hello"}],
        ]
    )

    result = await client.get_ticket_custom_fields(1)

    assert result == {"custom": {"customfield": "hello"}}


async def test_set_ticket_custom_fields_updates_existing_row(
    client: AsyncGlpiClient,
) -> None:
    """An existing value row is updated in place through the v1 session."""

    fake = _FakeV1(
        [
            [{"id": 1, "name": "custom", "itemtypes": '["Ticket"]'}],
            [{"id": 9, "plugin_fields_containers_id": 1, "name": "customfield"}],
            [{"id": 5, "customfield": "old"}],
            [{"5": True, "message": ""}],
        ]
    )
    client._v1 = fake  # type: ignore[assignment]

    await client.set_ticket_custom_fields(1, {"custom": {"customfield": "new"}})

    update = fake.calls[-1]
    assert update["method"] == "PUT"
    assert update["json_body"] == {"input": {"id": 5, "customfield": "new"}}


async def test_set_ticket_custom_fields_rejects_unknown_container(
    client: AsyncGlpiClient,
) -> None:
    """Unknown containers raise before any write."""

    client._v1 = _FakeV1(  # type: ignore[assignment]
        [[{"id": 1, "name": "custom", "itemtypes": '["Ticket"]'}]]
    )

    with pytest.raises(ValueError, match="Unknown plugin-fields container"):
        await client.set_ticket_custom_fields(1, {"nope": {"x": 1}})
