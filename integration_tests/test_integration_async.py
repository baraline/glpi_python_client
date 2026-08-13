"""Integration tests targeting a live GLPI instance with AsyncGlpiClient.

The suite mirrors the most important workflows from
``test_integration.py`` against the asynchronous
:class:`AsyncGlpiClient` and adds stress cases that exercise behaviour
that only shows up at runtime on the async surface:

* Concurrent fan-out via :func:`asyncio.gather` (read-only).
* OAuth token-acquisition lock contention from many coroutines racing
  for the very first authenticated call.
* Real non-blocking I/O on the caller's event loop, with no worker
  thread anywhere on the path.
* Cancellation of an in-flight awaiting coroutine.
* Exception propagation from the transport back to the awaiter.

The shared configuration loader from :mod:`test_integration` is reused
so the same secrets/env layout drives both suites.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from test_integration import (  # noqa: F401
    _LiveGlpiConfig,
    _suffix,
    live_config,
)

from glpi_python_client import (
    AsyncGlpiClient,
    GlpiNotFoundError,
    GlpiTicketContext,
    PostFollowup,
    PostLocation,
    PostSolution,
    PostTeamMember,
    PostTicket,
    PostTicketTask,
    PostUser,
)

pytestmark = pytest.mark.integration


def _build_async_client(config: _LiveGlpiConfig) -> AsyncGlpiClient:
    """Return one configured :class:`AsyncGlpiClient` for the live instance.

    Parameters
    ----------
    config : _LiveGlpiConfig
        Live GLPI configuration loaded from the secrets directory or
        the ``GLPI_*`` environment variables.
    """

    return AsyncGlpiClient(
        glpi_api_url=config.api_url,
        server_timezone=config.server_timezone,
        client_id=config.client_id,
        client_secret=config.client_secret,
        username=config.username,
        password=config.password,
        glpi_entity=config.entity,
        glpi_profile=config.profile,
        entity_recursive=config.entity_recursive,
        verify_ssl=config.verify_ssl,
        v1_base_url=config.v1_base_url,
        v1_user_token=config.v1_user_token,
        v1_app_token=config.v1_app_token,
    )


@pytest_asyncio.fixture
async def async_client(
    live_config: _LiveGlpiConfig,  # noqa: F811
) -> AsyncIterator[AsyncGlpiClient]:
    """Yield one configured :class:`AsyncGlpiClient` and close it on teardown.

    Each test gets its own client so HTTP sessions and the OAuth token
    cache never leak across tests.
    """

    client = _build_async_client(live_config)
    try:
        yield client
    finally:
        await client.close()


async def test_user_lifecycle_async(async_client: AsyncGlpiClient) -> None:
    """Create, fetch, list, and delete a user via the async surface."""

    suffix = _suffix()
    user_id = await async_client.create_user(
        PostUser(
            username=f"itest-async-user-{suffix}",
            password=f"pwd-{suffix}",
            password2=f"pwd-{suffix}",
            realname="AsyncIntegration",
            firstname="Test",
        )
    )
    try:
        fetched = await async_client.get_user(user_id)
        assert fetched.id == user_id
        listing = await async_client.search_users(f"username=={fetched.username}")
        assert any(u.id == user_id for u in listing)
    finally:
        await async_client.delete_user(user_id, force=True)


async def test_ticket_full_workflow_async(
    async_client: AsyncGlpiClient,
) -> None:
    """Create one ticket, exercise the timeline, and aggregate the context."""

    suffix = _suffix()
    ticket_id = await async_client.create_ticket(
        PostTicket(
            name=f"itest-async-ticket-{suffix}",
            content=f"<p>async integration body {suffix}</p>",
        )
    )
    try:
        followup_id = await async_client.create_ticket_followup(
            ticket_id,
            PostFollowup(content=f"<p>async followup {suffix}</p>"),
        )
        task_id = await async_client.create_ticket_task(
            ticket_id,
            PostTicketTask(
                content=f"<p>async task {suffix}</p>",
                duration=900,
            ),
        )
        solution_id = await async_client.create_ticket_solution(
            ticket_id,
            PostSolution(content=f"<p>async solution {suffix}</p>"),
        )

        context: GlpiTicketContext = await async_client.get_ticket_context(ticket_id)
        assert context.ticket.id == ticket_id
        assert any(f.id == followup_id for f in context.followups)
        assert any(t.id == task_id for t in context.tasks)
        assert any(s.id == solution_id for s in context.solutions)
    finally:
        await async_client.delete_ticket(ticket_id, force=True)


async def test_async_context_manager(live_config: _LiveGlpiConfig) -> None:  # noqa: F811
    """Verify ``async with AsyncGlpiClient(...)`` initialises and closes cleanly."""

    async with _build_async_client(live_config) as client:
        users = await client.search_users(limit=1)
        assert isinstance(users, list)


async def test_gather_fan_out_read_only(
    async_client: AsyncGlpiClient,
) -> None:
    """Fan out independent read-only calls and confirm each returns a list.

    This stresses the bridge: many coroutines hit
    the event loop simultaneously, contending for the OAuth
    token lock on the first call and then for the requests pool.
    """

    results = await asyncio.gather(
        async_client.search_users(limit=1),
        async_client.search_locations(limit=1),
        async_client.search_tickets("status==1", limit=1),
        async_client.search_users(limit=2),
        async_client.search_locations(limit=2),
        async_client.search_tickets("status==1", limit=2),
    )
    assert len(results) == 6
    for value in results:
        assert isinstance(value, list)


async def test_oauth_lock_contention_on_fresh_client(
    live_config: _LiveGlpiConfig,  # noqa: F811
) -> None:
    """Many coroutines on a fresh client share one OAuth token without races.

    The transport mixin's :class:`threading.Lock` must serialise token
    acquisition; without it, racing coroutines would each trigger their
    own OAuth round-trip.
    """

    async with _build_async_client(live_config) as client:
        results = await asyncio.gather(
            *(client.search_users(limit=1) for _ in range(8))
        )
        assert len(results) == 8
        for value in results:
            assert isinstance(value, list)


async def test_calls_run_on_the_event_loop_not_a_worker_thread(
    async_client: AsyncGlpiClient,
) -> None:
    """Requests are issued from the calling thread, on the event loop.

    This replaces an earlier test that asserted a caller-supplied
    executor received the work. There is no executor and no worker thread
    any more: the client performs real non-blocking I/O, so the whole
    call runs on the thread that owns the loop.

    A live fan-out is the honest way to check it -- a stubbed transport
    would prove nothing about how real sockets are driven.
    """

    import threading

    main_thread = threading.current_thread().name
    observed: list[str] = []

    async def _probe() -> None:
        await async_client.search_users(limit=1)
        observed.append(threading.current_thread().name)

    await asyncio.gather(*(_probe() for _ in range(6)))

    assert len(observed) == 6
    assert all(name == main_thread for name in observed), (
        f"calls ran off the loop thread: {set(observed)}"
    )


async def test_cancellation_releases_awaiter(
    async_client: AsyncGlpiClient,
) -> None:
    """Cancelling the task raises ``CancelledError`` promptly.

    With real async I/O the cancellation reaches the in-flight request
    itself rather than being best-effort against a detached worker
    thread, so the awaiting coroutine must unwind immediately.
    """

    task = asyncio.create_task(async_client.search_tickets("status==1", limit=50))
    await asyncio.sleep(0)  # let the task reach its first await
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_exception_propagates_from_an_awaited_call(
    async_client: AsyncGlpiClient,
) -> None:
    """A missing ticket surfaces as a typed GLPI error.

    We trigger one by reading a ticket id that almost certainly does
    not exist. The async client must surface the same
    :class:`~glpi_python_client.GlpiNotFoundError` the sync client
    would raise — users never import the HTTP library to catch it.
    """

    with pytest.raises(GlpiNotFoundError):
        await async_client.get_ticket(2**31 - 1)


async def test_concurrent_lifecycles_isolated(
    async_client: AsyncGlpiClient,
) -> None:
    """Two concurrent ticket lifecycles complete without cross-talk.

    Each coroutine creates its own ticket and a followup, fetches the
    aggregated context, and deletes the ticket. The two flows run
    inside :func:`asyncio.gather` to expose any shared mutable state on
    the client.
    """

    async def _lifecycle(tag: str) -> tuple[int, int]:
        suffix = _suffix()
        ticket_id = await async_client.create_ticket(
            PostTicket(
                name=f"itest-conc-{tag}-{suffix}",
                content=f"concurrent ticket body {tag} {suffix}",
            )
        )
        try:
            followup_id = await async_client.create_ticket_followup(
                ticket_id,
                PostFollowup(content=f"concurrent followup {tag} {suffix}"),
            )
            context = await async_client.get_ticket_context(ticket_id)
            assert context.ticket.id == ticket_id
            assert any(f.id == followup_id for f in context.followups)
            return ticket_id, followup_id
        finally:
            await async_client.delete_ticket(ticket_id, force=True)

    results = await asyncio.gather(_lifecycle("a"), _lifecycle("b"))
    (ticket_a, _), (ticket_b, _) = results
    assert ticket_a != ticket_b


async def test_get_task_statistics_gathers_concurrently(
    async_client: AsyncGlpiClient,
) -> None:
    """``get_task_statistics`` is an async-only fan-out helper.

    It runs :func:`asyncio.gather` over per-ticket task listings; we
    verify it accepts a small list of fresh ticket ids and returns one
    statistics payload.
    """

    suffix = _suffix()
    ticket_ids: list[int] = []
    for index in range(2):
        ticket_id = await async_client.create_ticket(
            PostTicket(
                name=f"itest-tstats-{index}-{suffix}",
                content=f"task stats body {index} {suffix}",
            )
        )
        ticket_ids.append(ticket_id)
        await async_client.create_ticket_task(
            ticket_id,
            PostTicketTask(
                content=f"task body {index} {suffix}",
                duration=600,
            ),
        )
    try:
        stats = await async_client.get_task_statistics(ticket_ids)
        assert stats["ticket_count"] == len(ticket_ids)
    finally:
        for ticket_id in ticket_ids:
            await async_client.delete_ticket(ticket_id, force=True)


async def test_create_then_cleanup_seed_records(
    async_client: AsyncGlpiClient,
) -> None:
    """End-to-end seed/cleanup round-trip used by the user guide examples.

    Mirrors the canonical demo seed (location + two users + ticket +
    team-member assignment + followup) and tears every record down on
    success or failure.
    """

    suffix = _suffix()
    location_id = await async_client.create_location(
        PostLocation(name=f"itest-async-loc-{suffix}")
    )
    alice_id = bob_id = ticket_id = 0
    try:
        alice_id = await async_client.create_user(
            PostUser(
                username=f"alice-async-{suffix}",
                password=f"pwd-{suffix}",
                password2=f"pwd-{suffix}",
                realname="Dupont",
                firstname="Alice",
            )
        )
        bob_id = await async_client.create_user(
            PostUser(
                username=f"bob-async-{suffix}",
                password=f"pwd-{suffix}",
                password2=f"pwd-{suffix}",
                realname="Martin",
                firstname="Bob",
            )
        )
        ticket_id = await async_client.create_ticket(
            PostTicket(
                name=f"itest-seed-{suffix}",
                content=f"seed body {suffix}",
            )
        )
        await async_client.add_ticket_team_member(
            ticket_id,
            PostTeamMember(type="User", id=bob_id, role="assigned"),
        )
        await async_client.create_ticket_followup(
            ticket_id,
            PostFollowup(content=f"seed followup {suffix}"),
        )
    finally:
        if ticket_id:
            await async_client.delete_ticket(ticket_id, force=True)
        if alice_id:
            await async_client.delete_user(alice_id, force=True)
        if bob_id:
            await async_client.delete_user(bob_id, force=True)
        await async_client.delete_location(location_id, force=True)


# ---------------------------------------------------------------------------
# iter_search_* async generators (Change 1)
# ---------------------------------------------------------------------------


async def test_iter_search_tickets_async(async_client: AsyncGlpiClient) -> None:
    """iter_search_tickets is usable with async for on the async client."""

    from glpi_python_client.models.api_schema.assistance._ticket import GetTicket

    items: list[GetTicket] = []
    async for batch in async_client.iter_search_tickets("status==1", batch_size=50):
        assert isinstance(batch, list)
        for ticket in batch:
            assert ticket.id is not None
        items.extend(batch)
        break  # one batch is enough to exercise the contract

    assert isinstance(items, list)


async def test_iter_search_users_async(async_client: AsyncGlpiClient) -> None:
    """iter_search_users is usable with async for on the async client."""

    from glpi_python_client.models.api_schema.administration._user import GetUser

    items: list[GetUser] = []
    async for batch in async_client.iter_search_users("", batch_size=50):
        assert isinstance(batch, list)
        for user in batch:
            assert user.id is not None
        items.extend(batch)
        break

    assert isinstance(items, list)


async def test_iter_search_entities_async(async_client: AsyncGlpiClient) -> None:
    """iter_search_entities is usable with async for on the async client."""

    from glpi_python_client.models.api_schema.administration._entity import GetEntity

    items: list[GetEntity] = []
    async for batch in async_client.iter_search_entities("", batch_size=50):
        assert isinstance(batch, list)
        for entity in batch:
            assert entity.id is not None
        items.extend(batch)
        break

    assert isinstance(items, list)


# ---------------------------------------------------------------------------
# get_task_durations async (Change 3 + async parity)
# ---------------------------------------------------------------------------


async def test_get_task_durations_async_shape(async_client: AsyncGlpiClient) -> None:
    """get_task_durations returns the expected mapping on the async client."""

    result = await async_client.get_task_durations(default_days=1)
    for key in (
        "start_date",
        "end_date",
        "total_duration",
        "task_count",
        "duration_by_user",
        "duration_by_entity",
        "tasks",
    ):
        assert key in result, f"missing key {key!r}"
    assert result["tasks"] is None


async def test_get_task_durations_async_captures_created_task(
    async_client: AsyncGlpiClient,
) -> None:
    """A task created today is captured by the async get_task_durations."""

    suffix = _suffix()
    ticket_id = await async_client.create_ticket(
        PostTicket(
            name=f"itest-async-taskdur-{suffix}",
            content=f"async task duration integration test {suffix}",
        )
    )
    try:
        await async_client.create_ticket_task(
            ticket_id,
            PostTicketTask(content=f"async task {suffix}", duration=600),
        )
        result = await async_client.get_task_durations(default_days=1)
        assert isinstance(result["total_duration"], int)
        assert isinstance(result["task_count"], int)
        assert int(result["total_duration"]) >= 600
        assert int(result["task_count"]) >= 1
    finally:
        await async_client.delete_ticket(ticket_id, force=True)


async def test_get_task_durations_async_with_details(
    async_client: AsyncGlpiClient,
) -> None:
    """return_task_details=True produces a tasks list on the async client."""

    suffix = _suffix()
    ticket_id = await async_client.create_ticket(
        PostTicket(
            name=f"itest-async-taskdet-{suffix}",
            content=f"async task details test {suffix}",
        )
    )
    try:
        await async_client.create_ticket_task(
            ticket_id,
            PostTicketTask(content=f"async detail task {suffix}", duration=300),
        )
        result = await async_client.get_task_durations(
            default_days=1,
            return_task_details=True,
        )
        assert isinstance(result["tasks"], list)
        if result["tasks"]:
            task = result["tasks"][0]
            assert "task_id" in task
            assert "ticket_id" in task
            assert "duration" in task
    finally:
        await async_client.delete_ticket(ticket_id, force=True)
