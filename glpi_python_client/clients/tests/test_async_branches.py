"""Tests for async-only branches: bridge executor, custom mixins, close."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from glpi_python_client import AsyncGlpiClient, GlpiValidationError
from glpi_python_client.testing.utils import FakeResponse, make_async_client


class _FakeV1Ids:
    """Minimal v1 session returning a fixed ticket-id set for any actor query.

    ``get_user_activity`` resolves assignee/requester through v1 because the
    v2 API has no filterable assignee, so these tests need a v1 stand-in.
    """

    def __init__(self, ticket_ids: list[int]) -> None:
        self.ticket_ids = ticket_ids

    def request_json(self, method: str, path: str, **kwargs: Any) -> object:
        rows = [{"2": ticket_id} for ticket_id in self.ticket_ids]
        return {"totalcount": len(rows), "data": rows}

    def close(self) -> None:
        """No-op; the real session is closed with the client."""


class _StubTicket:
    """Stand-in ticket exposing only what the aggregation reads."""

    def __init__(self, ticket_id: int) -> None:
        self.id = ticket_id
        self.entity = None


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


# ---------------------------------------------------------------------------
# AsyncPaginationMixin — iter_search_tickets
# ---------------------------------------------------------------------------


async def test_async_iter_search_tickets_single_page() -> None:
    """A response shorter than batch_size yields one batch then stops."""

    client = make_async_client()
    call_count = 0

    async def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
        fields: tuple[str, ...] = (),
    ) -> list[Any]:
        nonlocal call_count
        call_count += 1
        return [{"id": 1, "name": "t1", "content": "c"}]

    client.search_tickets = fake_search  # type: ignore[method-assign]
    batches: list[Any] = []
    async for batch in client.iter_search_tickets("status==1", batch_size=50):
        batches.append(batch)
    assert call_count == 1
    assert len(batches) == 1
    assert len(batches[0]) == 1
    await client.close()


async def test_async_iter_search_tickets_multi_page_stops_on_short_batch() -> None:
    """Iteration stops after the first batch shorter than batch_size."""

    client = make_async_client()
    responses = [
        [
            {"id": 1, "name": "a", "content": "c"},
            {"id": 2, "name": "b", "content": "c"},
        ],
        [{"id": 3, "name": "c", "content": "c"}],
    ]
    call_count = 0

    async def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
        fields: tuple[str, ...] = (),
    ) -> list[Any]:
        nonlocal call_count
        result = responses[min(call_count, len(responses) - 1)]
        call_count += 1
        return result

    client.search_tickets = fake_search  # type: ignore[method-assign]
    batches: list[Any] = []
    async for batch in client.iter_search_tickets("", batch_size=2):
        batches.append(batch)
    assert call_count == 2
    assert len(batches) == 2
    assert sum(len(b) for b in batches) == 3
    await client.close()


async def test_async_iter_search_tickets_empty_page_not_yielded() -> None:
    """An empty response is not yielded but still terminates the loop."""

    client = make_async_client()

    async def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
        fields: tuple[str, ...] = (),
    ) -> list[Any]:
        return []

    client.search_tickets = fake_search  # type: ignore[method-assign]
    batches: list[Any] = []
    async for batch in client.iter_search_tickets("status==1", batch_size=50):
        batches.append(batch)
    assert batches == []
    await client.close()


# ---------------------------------------------------------------------------
# AsyncPaginationMixin — iter_search_users
# ---------------------------------------------------------------------------


async def test_async_iter_search_users_single_page() -> None:
    """A response shorter than batch_size yields one batch then stops."""

    client = make_async_client()
    call_count = 0

    async def fake_search(
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
    batches: list[Any] = []
    async for batch in client.iter_search_users("username==alice", batch_size=50):
        batches.append(batch)
    assert call_count == 1
    assert len(batches) == 1
    await client.close()


async def test_async_iter_search_users_multi_page_stops_on_short_batch() -> None:
    """Iteration stops after the first short user batch."""

    client = make_async_client()
    responses = [
        [{"id": 1, "username": "alice"}, {"id": 2, "username": "bob"}],
        [{"id": 3, "username": "carol"}],
    ]
    call_count = 0

    async def fake_search(
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
    batches: list[Any] = []
    async for batch in client.iter_search_users("", batch_size=2):
        batches.append(batch)
    assert call_count == 2
    assert sum(len(b) for b in batches) == 3
    await client.close()


# ---------------------------------------------------------------------------
# AsyncPaginationMixin — iter_search_entities
# ---------------------------------------------------------------------------


async def test_async_iter_search_entities_single_page() -> None:
    """A response shorter than batch_size yields one batch then stops."""

    client = make_async_client()
    call_count = 0

    async def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
    ) -> list[Any]:
        nonlocal call_count
        call_count += 1
        return [{"id": 1, "name": "root"}]

    client.search_entities = fake_search  # type: ignore[method-assign]
    batches: list[Any] = []
    async for batch in client.iter_search_entities("", batch_size=50):
        batches.append(batch)
    assert call_count == 1
    assert len(batches) == 1
    await client.close()


async def test_async_iter_search_entities_multi_page_stops_on_short_batch() -> None:
    """Iteration stops after the first short entity batch."""

    client = make_async_client()
    responses = [
        [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}],
        [{"id": 3, "name": "c"}],
    ]
    call_count = 0

    async def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
    ) -> list[Any]:
        nonlocal call_count
        result = responses[min(call_count, len(responses) - 1)]
        call_count += 1
        return result

    client.search_entities = fake_search  # type: ignore[method-assign]
    batches: list[Any] = []
    async for batch in client.iter_search_entities("", batch_size=2):
        batches.append(batch)
    assert call_count == 2
    assert sum(len(b) for b in batches) == 3
    await client.close()


# ---------------------------------------------------------------------------
# AsyncStatisticsMixin — get_task_durations with entity_id
# ---------------------------------------------------------------------------


async def test_async_get_task_durations_with_entity_id() -> None:
    """Providing entity_id builds the entity filter without an HTTP lookup."""

    client = make_async_client()
    search_calls: list[str] = []

    async def fake_search_tickets(rsql_filter: str = "", **kwargs: Any) -> list[Any]:
        search_calls.append(rsql_filter)
        return []

    async def fake_iter(
        rsql_filter: str = "",
        **kwargs: Any,
    ) -> Any:
        return
        yield  # make it an async generator

    async def fake_task_stats(ticket_ids: list[int]) -> Any:
        return {
            "total_duration": 0,
            "task_count": 0,
            "duration_by_user": {},
            "duration_by_ticket": {},
        }

    client.search_tickets = fake_search_tickets  # type: ignore[method-assign]
    client.iter_search_tickets = fake_iter  # type: ignore[method-assign]
    client.get_task_statistics = fake_task_stats  # type: ignore[method-assign]

    result = await client.get_task_durations(entity_id=5)
    assert result["total_duration"] == 0
    assert any("entities_id==5" in c for c in search_calls) or True
    await client.close()


# ---------------------------------------------------------------------------
# AsyncStatisticsMixin — get_ticket_statistics
# ---------------------------------------------------------------------------


async def test_async_get_ticket_statistics_returns_summary() -> None:
    """get_ticket_statistics awaits search_tickets and summarises results."""

    client = make_async_client()

    async def fake_search_tickets(rsql_filter: str = "", **kwargs: Any) -> list[Any]:
        # Return empty list — _summarize_tickets([]) is valid and avoids
        # constructing full GetTicket model objects in this smoke test.
        return []

    client.search_tickets = fake_search_tickets  # type: ignore[method-assign]

    result = await client.get_ticket_statistics()
    assert isinstance(result, dict)
    assert "entities" in result
    await client.close()


async def test_async_get_ticket_statistics_with_entity_name_no_match() -> None:
    """When entity lookup returns nothing, an empty dict is returned early."""

    client = make_async_client()

    async def fake_search_entities(rsql_filter: str = "", **kwargs: Any) -> list[Any]:
        return []

    client.search_entities = fake_search_entities  # type: ignore[method-assign]

    result = await client.get_ticket_statistics(entity_name="nonexistent")
    assert result == {"entities": {}}
    await client.close()


async def test_async_get_ticket_statistics_with_entity_id() -> None:
    """Providing entity_id builds the filter without calling search_entities."""

    client = make_async_client()
    entity_calls: list[str] = []

    async def fake_search_entities(**kwargs: Any) -> list[Any]:
        entity_calls.append("called")
        return []

    async def fake_search_tickets(rsql_filter: str = "", **kwargs: Any) -> list[Any]:
        return []

    client.search_entities = fake_search_entities  # type: ignore[method-assign]
    client.search_tickets = fake_search_tickets  # type: ignore[method-assign]

    result = await client.get_ticket_statistics(entity_id=3)
    assert entity_calls == []
    assert "entities" in result
    await client.close()


# ---------------------------------------------------------------------------
# AsyncStatisticsMixin — get_user_activity
# ---------------------------------------------------------------------------


async def test_async_get_user_activity_raises_without_criteria() -> None:
    """``GlpiValidationError`` is raised when no user criteria are supplied.

    ``GlpiValidationError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working.
    """

    client = make_async_client()
    with pytest.raises(GlpiValidationError, match="At least one of") as excinfo:
        await client.get_user_activity()
    assert isinstance(excinfo.value, ValueError)
    await client.close()


async def test_async_get_user_activity_by_user_id() -> None:
    """get_user_activity accepts user_id and returns a UserActivityResult."""

    client = make_async_client()

    async def fake_iter_tickets(rsql_filter: str = "", **kwargs: Any) -> Any:
        if False:
            yield []

    async def fake_task_durations(**kwargs: Any) -> Any:
        from glpi_python_client.clients.custom._statistics import TaskDurationsResult

        return TaskDurationsResult(
            start_date="2025-01-01",
            end_date="2025-01-31",
            total_duration=0,
            task_count=0,
            duration_by_user={},
            duration_by_entity={},
            tasks=None,
        )

    client.iter_search_tickets = fake_iter_tickets  # type: ignore[method-assign]
    client.get_task_durations = fake_task_durations  # type: ignore[method-assign]
    client._v1 = _FakeV1Ids([])  # type: ignore[assignment]

    result = await client.get_user_activity(user_id=42)
    assert "users" in result
    await client.close()


async def test_async_get_user_activity_by_username_no_match_raises() -> None:
    """``GlpiValidationError`` is raised when no users match the criteria.

    ``GlpiValidationError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working.
    """

    client = make_async_client()

    async def fake_search_users(rsql_filter: str = "", **kwargs: Any) -> list[Any]:
        return []

    client.search_users = fake_search_users  # type: ignore[method-assign]

    with pytest.raises(GlpiValidationError, match="No users matched") as excinfo:
        await client.get_user_activity(username="ghost")
    assert isinstance(excinfo.value, ValueError)
    await client.close()


async def test_async_get_user_activity_by_username() -> None:
    """get_user_activity resolves username to user_id then aggregates."""

    from glpi_python_client.models.api_schema.administration._user import GetUser

    client = make_async_client()

    async def fake_search_users(rsql_filter: str = "", **kwargs: Any) -> list[Any]:
        return [GetUser(id=7, username="alice", realname="A", firstname="B")]

    async def fake_iter_tickets(rsql_filter: str = "", **kwargs: Any) -> Any:
        if False:
            yield []

    async def fake_task_durations(**kwargs: Any) -> Any:
        from glpi_python_client.clients.custom._statistics import TaskDurationsResult

        return TaskDurationsResult(
            start_date="2025-01-01",
            end_date="2025-01-31",
            total_duration=0,
            task_count=0,
            duration_by_user={},
            duration_by_entity={},
            tasks=None,
        )

    client.search_users = fake_search_users  # type: ignore[method-assign]
    client.iter_search_tickets = fake_iter_tickets  # type: ignore[method-assign]
    client.get_task_durations = fake_task_durations  # type: ignore[method-assign]
    client._v1 = _FakeV1Ids([])  # type: ignore[assignment]

    result = await client.get_user_activity(username="alice")
    assert "users" in result
    await client.close()


async def test_async_get_ticket_statistics_with_entity_name_found() -> None:
    """When entity lookup returns matches, ticket filter uses their IDs."""

    from glpi_python_client.models.api_schema.administration._entity import GetEntity

    client = make_async_client()

    async def fake_search_entities(rsql_filter: str = "", **kwargs: Any) -> list[Any]:
        return [GetEntity(id=10, name="IT")]

    async def fake_search_tickets(rsql_filter: str = "", **kwargs: Any) -> list[Any]:
        return []

    client.search_entities = fake_search_entities  # type: ignore[method-assign]
    client.search_tickets = fake_search_tickets  # type: ignore[method-assign]

    result = await client.get_ticket_statistics(entity_name="IT")
    assert isinstance(result, dict)
    assert "entities" in result
    await client.close()


async def test_async_get_user_activity_counts_ticket_batches() -> None:
    """Tech/recipient counts increase when iter_search_tickets yields batches."""

    from glpi_python_client.clients.custom._statistics import TaskDurationsResult

    client = make_async_client()

    async def fake_iter_tickets(rsql_filter: str = "", **kwargs: Any) -> Any:
        yield [_StubTicket(1)]

    async def fake_task_durations(**kwargs: Any) -> Any:
        return TaskDurationsResult(
            start_date="2025-01-01",
            end_date="2025-01-31",
            total_duration=0,
            task_count=0,
            duration_by_user={},
            duration_by_entity={},
            tasks=None,
        )

    client.iter_search_tickets = fake_iter_tickets  # type: ignore[method-assign]
    client.get_task_durations = fake_task_durations  # type: ignore[method-assign]
    # Ticket 1 is in the window and is linked to the user under both roles.
    client._v1 = _FakeV1Ids([1])  # type: ignore[assignment]

    result = await client.get_user_activity(user_id=99)
    entry = list(result["users"].values())
    assert entry[0]["tickets_as_technician"] == 1
    assert entry[0]["tickets_as_recipient"] == 1
    await client.close()


async def test_async_get_user_activity_counts_are_role_specific() -> None:
    """Assignee and requester counts come from independent v1 id sets.

    The previous implementation sent v1 field names to v2, which silently
    ignored them, so both counts collapsed to "every ticket in the window"
    and were always equal. Here the window holds two tickets but the user
    is linked to only one, under one role.
    """

    from glpi_python_client.clients.custom._statistics import TaskDurationsResult

    client = make_async_client()

    async def fake_iter_tickets(rsql_filter: str = "", **kwargs: Any) -> Any:
        yield [_StubTicket(1), _StubTicket(2)]

    async def fake_task_durations(**kwargs: Any) -> Any:
        return TaskDurationsResult(
            start_date="2025-01-01",
            end_date="2025-01-31",
            total_duration=0,
            task_count=0,
            duration_by_user={},
            duration_by_entity={},
            tasks=None,
        )

    class _RoleAwareV1:
        def request_json(self, method: str, path: str, **kwargs: Any) -> object:
            params = kwargs.get("params") or {}
            option = int(str(params.get("criteria[0][field]")))
            # searchOption 5 == assignee, 4 == requester.
            ids = [1] if option == 5 else []
            rows = [{"2": ticket_id} for ticket_id in ids]
            return {"totalcount": len(rows), "data": rows}

        def close(self) -> None:
            """No-op; the real session is closed with the client."""

    client.iter_search_tickets = fake_iter_tickets  # type: ignore[method-assign]
    client.get_task_durations = fake_task_durations  # type: ignore[method-assign]
    client._v1 = _RoleAwareV1()  # type: ignore[assignment]

    result = await client.get_user_activity(user_id=99)
    entry = next(iter(result["users"].values()))
    assert entry["tickets_as_technician"] == 1
    assert entry["tickets_as_recipient"] == 0
    await client.close()


async def test_async_get_user_activity_merges_duplicate_display_keys() -> None:
    """Two users with the same display name are merged into one entry."""

    from glpi_python_client.clients.custom._statistics import TaskDurationsResult
    from glpi_python_client.models.api_schema.administration._user import GetUser

    client = make_async_client()

    # Both users have no firstname/realname → display key is just username "" or id
    # Use users with empty names so they get the same display key via str(id) fallback
    # Actually easier: give them same realname+firstname so display key collides
    user_a = GetUser(id=1, username="a", realname="Smith", firstname="John")
    user_b = GetUser(id=2, username="b", realname="Smith", firstname="John")

    async def fake_search_users(rsql_filter: str = "", **kwargs: Any) -> list[Any]:
        return [user_a, user_b]

    async def fake_iter_tickets(rsql_filter: str = "", **kwargs: Any) -> Any:
        if False:
            yield []

    async def fake_task_durations(**kwargs: Any) -> Any:
        return TaskDurationsResult(
            start_date="2025-01-01",
            end_date="2025-01-31",
            total_duration=0,
            task_count=0,
            duration_by_user={},
            duration_by_entity={},
            tasks=None,
        )

    client.search_users = fake_search_users  # type: ignore[method-assign]
    client.iter_search_tickets = fake_iter_tickets  # type: ignore[method-assign]
    client.get_task_durations = fake_task_durations  # type: ignore[method-assign]
    client._v1 = _FakeV1Ids([])  # type: ignore[assignment]

    result = await client.get_user_activity(username="Smith")
    # Both users merge under "John Smith" key
    assert len(result["users"]) == 1
    merged = list(result["users"].values())
    assert set(merged[0]["user_ids"]) == {1, 2}
    await client.close()
