"""Runtime tests for the hand-written async surface.

The bulk of the suite exercises the generated sync client, which is a 1:1
token transform of this tree and therefore covers the shared logic. What it
cannot cover is anything that only exists once ``async``/``await`` are real:
whether the client actually awaits, whether concurrent tasks can contend the
auth lock without deadlocking, and whether the fan-out helper really runs
work concurrently rather than in sequence.

Those are exactly the properties the codegen cannot verify -- the diff gate
proves the two trees *correspond*, not that the async one *works* -- so they
are tested here directly.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pytest

from glpi_python_client import AsyncGlpiClient, GlpiTimeoutError, GlpiTransportError
from glpi_python_client._async._concurrency import gather
from glpi_python_client.testing.utils import make_async_client


class _Response:
    """Minimal response object covering what the transport layer reads."""

    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        self.text = "{}"
        self.reason = "OK"
        self.url = "https://glpi.example.test/api.php/v2/stub"
        self.content = b"{}"

    def json(self) -> Any:
        return self._payload


def _stub(client: AsyncGlpiClient, payload: Any) -> list[str]:
    """Install an async transport stub and pretend a token is held."""

    calls: list[str] = []

    async def _request(method: str, url: str, **kwargs: Any) -> _Response:
        calls.append(f"{method} {url}")
        return _Response(payload)

    client._session.request = _request  # type: ignore[method-assign,assignment]
    client._auth.access_token = "stub-token"
    client._auth.token_expires_at = datetime.now(tz=timezone.utc) + timedelta(days=365)
    return calls


async def test_a_read_awaits_and_returns_a_model() -> None:
    """The async client dispatches and parses exactly like its twin."""

    client = make_async_client()
    calls = _stub(client, {"id": 42, "name": "async ticket"})
    try:
        ticket = await client.get_ticket(42)
        assert ticket.id == 42
        assert ticket.name == "async ticket"
        assert calls, "no HTTP call was dispatched"
    finally:
        await client.close()


async def test_close_is_idempotent_and_blocks_further_calls() -> None:
    """Closing twice is safe and a closed client refuses to dispatch."""

    client = make_async_client()
    _stub(client, {"id": 1, "name": "x"})
    await client.close()
    await client.close()
    with pytest.raises(RuntimeError, match="closed"):
        await client.get_ticket(1)


async def test_the_async_context_manager_closes_on_exit() -> None:
    """``async with`` releases the client, so ``__aexit__`` really awaits."""

    client = make_async_client()
    _stub(client, {"id": 1, "name": "x"})
    async with client as entered:
        assert entered is client
    assert client._closed is True


async def test_concurrent_tasks_contend_the_auth_lock_without_deadlocking() -> None:
    """Many tasks may refresh the token at once and all of them finish.

    This is the property the hand-written ``_concurrency`` twin exists for.
    The lock is held across an ``await``; with a ``threading.Lock`` -- the
    right primitive for the *sync* tree -- the second task to arrive would
    block the event loop, the holder could never resume to release it, and
    this test would hang forever rather than fail. Running real contention
    is the only way to observe that.
    """

    client = make_async_client()
    calls = _stub(client, {"id": 1, "name": "x"})
    # Force every task through the token-acquisition path.
    client._auth.access_token = None

    acquisitions = 0

    async def _acquire() -> None:
        nonlocal acquisitions
        acquisitions += 1
        await asyncio.sleep(0)  # a real suspension point inside the lock
        client._auth.access_token = "stub-token"

    client._auth._acquire_token = _acquire  # type: ignore[method-assign]
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*(client.get_ticket(i) for i in range(1, 11))),
            timeout=10,
        )
        assert len(results) == 10
        assert len(calls) == 10
    finally:
        await client.close()


async def test_gather_runs_work_concurrently() -> None:
    """The async ``gather`` overlaps its arguments rather than serialising.

    The sync twin returns already-evaluated values, which is correct there.
    Here the whole point is that the calls overlap.

    Completion *order* is the primary evidence: the shorter sleep finishes
    first even though it is passed second, which cannot happen if the two
    ran one after the other. The elapsed-time bound is a secondary check,
    and the delays are chosen well clear of the platform timer granularity
    (~16ms on Windows) so the margin between "concurrent" and "sequential"
    is not swallowed by rounding.
    """

    slow_delay, fast_delay = 0.30, 0.15
    order: list[str] = []

    async def _sleep_then_record(label: str, delay: float) -> str:
        await asyncio.sleep(delay)
        order.append(label)
        return label

    loop = asyncio.get_running_loop()
    started = loop.time()
    results = await gather(
        _sleep_then_record("slow", slow_delay),
        _sleep_then_record("fast", fast_delay),
    )
    elapsed = loop.time() - started

    # Results keep argument order; completion order is by speed.
    assert results == ["slow", "fast"]
    assert order == ["fast", "slow"], "the two coroutines did not overlap"
    assert elapsed < (slow_delay + fast_delay) * 0.9, (
        f"gather took {elapsed:.3f}s, close to the sequential "
        f"{slow_delay + fast_delay:.3f}s -- it serialised its arguments"
    )


async def test_network_faults_are_translated_on_the_async_path() -> None:
    """A transport fault surfaces as a library error, not an httpx one.

    The sync path has its own test for this. Repeating it here is not
    duplication: the translation sits in a ``try``/``except`` around an
    awaited call, and an ``except`` clause that fails to cover an awaited
    expression is a distinct mistake the sync test cannot detect.
    """

    client = make_async_client()
    _stub(client, {})

    async def _boom(method: str, url: str, **kwargs: Any) -> _Response:
        raise httpx.ConnectError("network down")

    client._session.request = _boom  # type: ignore[method-assign,assignment]
    # Keep the retry from spending 6 real seconds on the way to failing.
    client._get_request.retry.wait = lambda *a, **k: 0  # type: ignore[attr-defined]
    try:
        with pytest.raises(GlpiTransportError) as excinfo:
            await client.get_ticket(1)
        assert isinstance(excinfo.value.__cause__, httpx.ConnectError)
    finally:
        await client.close()


async def test_timeouts_narrow_on_the_async_path() -> None:
    """A timeout narrows to ``GlpiTimeoutError`` when awaited too."""

    client = make_async_client()
    _stub(client, {})

    async def _slow(method: str, url: str, **kwargs: Any) -> _Response:
        raise httpx.ConnectTimeout("too slow")

    client._session.request = _slow  # type: ignore[method-assign,assignment]
    client._get_request.retry.wait = lambda *a, **k: 0  # type: ignore[attr-defined]
    try:
        with pytest.raises(GlpiTimeoutError):
            await client.get_ticket(1)
    finally:
        await client.close()


async def test_the_paginating_generator_is_an_async_generator() -> None:
    """``iter_search_*`` yields pages under ``async for``.

    The generators are the one place the codegen has to get two things
    right at once -- ``async def`` plus ``AsyncIterator`` -- and a mistake
    in either shows up only when the generator is actually driven.
    """

    client = make_async_client()
    _stub(client, [{"id": 1, "name": "one"}])
    try:
        pages = []
        async for page in client.iter_search_tickets(batch_size=50):
            pages.append(page)
            break
        assert pages and pages[0][0].id == 1
    finally:
        await client.close()
