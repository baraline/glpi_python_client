"""Tests for async-only branches: bridge executor, custom mixins, close."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from glpi_python_client import AsyncGlpiClient
from glpi_python_client.testing.utils import FakeResponse, make_async_client


async def test_async_bridge_uses_provided_executor() -> None:
    """A custom executor is used to dispatch the wrapped sync call."""

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="glpi-test") as pool:
        client = make_async_client(executor=pool)
        captured: dict[str, str] = {}

        def _get(
            endpoint: str, params: Any = None, skip_entity: bool = False
        ) -> FakeResponse:
            import threading

            captured["thread"] = threading.current_thread().name
            return FakeResponse(status_code=200, payload=[])

        client._get_request = _get  # type: ignore[method-assign]
        await client.search_tickets("status==1")
        await client.close()
    assert captured["thread"].startswith("glpi-test")


async def test_async_get_ticket_context_fan_out_uses_gather() -> None:
    """The async override aggregates the five endpoint coroutines concurrently."""

    client = make_async_client()
    calls: list[str] = []

    def _get(
        endpoint: str, params: Any = None, skip_entity: bool = False
    ) -> FakeResponse:
        calls.append(endpoint)
        if endpoint.endswith("/Timeline/Followup"):
            return FakeResponse(status_code=200, payload=[])
        if endpoint.endswith("/Timeline/Solution"):
            return FakeResponse(status_code=200, payload=[])
        if endpoint.endswith("/Timeline/Task"):
            return FakeResponse(status_code=200, payload=[])
        if endpoint.endswith("/Timeline/Document"):
            return FakeResponse(status_code=200, payload=[])
        return FakeResponse(
            status_code=200,
            payload={"id": 42, "name": "t", "content": "<p>c</p>"},
        )

    client._get_request = _get  # type: ignore[method-assign]
    ctx = await client.get_ticket_context(42)
    assert ctx.ticket.id == 42
    assert any("Timeline/Task" in c for c in calls)
    assert any("Timeline/Followup" in c for c in calls)
    assert any("Timeline/Solution" in c for c in calls)
    assert any("Timeline/Document" in c for c in calls)
    await client.close()


async def test_async_get_task_statistics_with_tickets_uses_gather() -> None:
    """The async override fetches per-ticket tasks concurrently."""

    client = make_async_client()
    seen: list[str] = []

    def _get(
        endpoint: str, params: Any = None, skip_entity: bool = False
    ) -> FakeResponse:
        seen.append(endpoint)
        return FakeResponse(status_code=200, payload=[])

    client._get_request = _get  # type: ignore[method-assign]
    stats = await client.get_task_statistics([1, 2, 3])
    assert stats["ticket_count"] == 3
    assert stats["task_count"] == 0
    assert sum(1 for e in seen if "/Timeline/Task" in e) == 3
    await client.close()


async def test_async_get_task_statistics_empty_short_circuits() -> None:
    """An empty ticket list returns zeroed totals without HTTP traffic."""

    client = make_async_client()

    def _fail(*_args: Any, **_kwargs: Any) -> FakeResponse:
        pytest.fail("no HTTP call expected for empty ticket list")

    client._get_request = _fail  # type: ignore[method-assign]
    stats = await client.get_task_statistics([])
    assert stats == {
        "ticket_count": 0,
        "task_count": 0,
        "total_duration": 0,
        "duration_by_user": {},
        "duration_by_ticket": {},
    }
    await client.close()


async def test_async_close_closes_v1_session_when_configured() -> None:
    """The async ``close`` also closes the optional v1 fallback session."""

    client = AsyncGlpiClient(
        glpi_api_url="https://glpi.example.test/api.php/v2",
        username="u",
        password="p",
        v1_base_url="https://glpi.example.test/apirest.php",
        v1_user_token="user-token",
        v1_app_token="app-token",
    )
    assert client._v1 is not None
    await client.close()
    assert client._closed is True


async def test_async_from_env_accepts_executor() -> None:
    """``AsyncGlpiClient.from_env`` accepts an executor and forwards it."""

    env = {
        "GLPI_API_URL": "https://glpi.example.test/api.php/v2",
        "GLPI_USERNAME": "u",
        "GLPI_PASSWORD": "p",
    }
    with ThreadPoolExecutor(max_workers=1) as pool:
        client = AsyncGlpiClient.from_env(env=env, executor=pool)
        try:
            assert client._executor is pool
        finally:
            await client.close()


async def test_async_generator_wrapper_yields_then_stops_default_executor() -> None:
    """The bridge wrapper drives a sync generator function to completion."""

    from glpi_python_client.clients.commons._async_bridge import (
        AsyncBridge,
        _make_async_generator_wrapper,
    )

    def sync_gen(self: AsyncBridge, n: int) -> Any:
        for i in range(n):
            yield [i]

    wrapper = _make_async_generator_wrapper(sync_gen)

    class _Owner(AsyncBridge):
        pass

    owner = _Owner()
    collected: list[list[int]] = []
    async for batch in wrapper(owner, 3):
        collected.append(batch)
    assert collected == [[0], [1], [2]]


async def test_async_generator_wrapper_with_executor() -> None:
    """The wrapper dispatches generator advancement to the supplied executor."""

    from glpi_python_client.clients.commons._async_bridge import (
        AsyncBridge,
        _make_async_generator_wrapper,
    )

    captured_threads: list[str] = []

    def sync_gen(self: AsyncBridge) -> Any:
        import threading

        captured_threads.append(threading.current_thread().name)
        yield ["one"]
        captured_threads.append(threading.current_thread().name)

    wrapper = _make_async_generator_wrapper(sync_gen)

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="glpi-gen") as pool:

        class _Owner(AsyncBridge):
            pass

        owner = _Owner()
        owner._executor = pool
        batches: list[list[str]] = []
        async for batch in wrapper(owner):
            batches.append(batch)
    assert batches == [["one"]]
    assert captured_threads
    assert all(name.startswith("glpi-gen") for name in captured_threads)
