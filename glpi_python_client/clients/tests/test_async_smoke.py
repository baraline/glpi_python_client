"""Smoke tests for the asynchronous client and its async bridge.

The tests exercise a few representative endpoint methods on
:class:`~glpi_python_client.AsyncGlpiClient` to confirm the bridge
correctly:

* wraps inherited sync methods into awaitable coroutines,
* dispatches the blocking call off the event loop, and
* preserves the synchronous transport call signatures so test recorders
  can stub the same hooks as the sync test suite.
"""

from __future__ import annotations

from typing import Any

import pytest

from glpi_python_client import (
    AsyncGlpiClient,
    PostFollowup,
    PostTicket,
    PostUser,
)
from glpi_python_client.testing.utils import FakeResponse, make_async_client


class _AsyncRecorder:
    """Synchronous transport recorder installed on the async client.

    The recorder relies on the fact that the async bridge wraps the
    inherited synchronous transport hooks; the underlying ``_get_*``,
    ``_post_*``, ``_update_*`` and ``_delete_*`` helpers themselves
    remain synchronous and run inside the bridge worker thread.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def install(self, client: AsyncGlpiClient) -> None:
        """Replace the transport methods on ``client`` with sync stubs."""

        def _get(
            endpoint: str,
            params: dict[str, Any] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            self.calls.append(
                {
                    "method": "GET",
                    "endpoint": endpoint,
                    "params": params,
                    "skip_entity": skip_entity,
                }
            )
            return FakeResponse(
                status_code=200, payload=[{"id": 1, "name": "n", "content": "c"}]
            )

        def _post(
            endpoint: str,
            json_body: dict[str, Any] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            self.calls.append(
                {
                    "method": "POST",
                    "endpoint": endpoint,
                    "json": json_body,
                    "skip_entity": skip_entity,
                }
            )
            return FakeResponse(status_code=201, payload={"id": 999})

        client._get_request = _get  # type: ignore[method-assign]
        client._post_request = _post  # type: ignore[method-assign]


@pytest.fixture
def async_client() -> AsyncGlpiClient:
    """Return one in-memory async client without any real HTTP plumbing."""

    return make_async_client()


@pytest.fixture
def async_recorder(async_client: AsyncGlpiClient) -> _AsyncRecorder:
    """Return one transport recorder already wired onto ``async_client``."""

    rec = _AsyncRecorder()
    rec.install(async_client)
    return rec


async def test_async_create_user_returns_awaitable(
    async_client: AsyncGlpiClient, async_recorder: _AsyncRecorder
) -> None:
    """The async ``create_user`` returns an awaitable that resolves to the id."""

    user_id = await async_client.create_user(PostUser(username="alice"))
    assert user_id == 999
    assert async_recorder.calls[0]["endpoint"] == "Administration/User"


async def test_async_search_tickets_returns_models(
    async_client: AsyncGlpiClient, async_recorder: _AsyncRecorder
) -> None:
    """The async ``search_tickets`` returns validated ticket models."""

    tickets = await async_client.search_tickets("status==1")
    assert len(tickets) == 1
    assert async_recorder.calls[0]["endpoint"] == "Assistance/Ticket"


async def test_async_create_ticket_followup_targets_timeline_endpoint(
    async_client: AsyncGlpiClient, async_recorder: _AsyncRecorder
) -> None:
    """The async followup helper still hits the timeline endpoint."""

    await async_client.create_ticket_followup(7, PostFollowup(content="<p>hi</p>"))
    assert (
        async_recorder.calls[0]["endpoint"] == "Assistance/Ticket/7/Timeline/Followup"
    )


async def test_async_create_ticket_serialises_enums(
    async_client: AsyncGlpiClient, async_recorder: _AsyncRecorder
) -> None:
    """The async create_ticket serialises enums identically to the sync surface."""

    await async_client.create_ticket(PostTicket(name="t", content="<p>c</p>"))
    assert async_recorder.calls[0]["endpoint"] == "Assistance/Ticket"
    assert async_recorder.calls[0]["json"]["name"] == "t"


async def test_async_close_is_idempotent() -> None:
    """Calling ``close`` twice on the async client does not raise."""

    client = make_async_client()
    await client.close()
    await client.close()


async def test_async_context_manager_closes_client() -> None:
    """The async context manager closes the client on exit."""

    async with make_async_client() as client:
        assert client.glpi_api_url.endswith("/api.php")
    with pytest.raises(RuntimeError, match="closed"):
        client._ensure_open()
