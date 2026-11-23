"""Concurrency tests for :class:`GLPIV1Session` on the sync surface.

Hand-written on both sides of the codegen (see ``HAND_WRITTEN`` in
``unasync_build.py``): the async twin of this module drives the same
scenarios from tasks, this one from threads sharing one session.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import httpx

from glpi_python_client._sync.auth._v1_session import GLPIV1Session
from glpi_python_client.testing.utils import FakeResponse

_THREADS = 8


class _ServerSimulation:
    """Fake v1 server that tracks which session tokens are alive.

    ``killSession`` answers 401 for a token that is already dead, and any
    other call answers 401 for a dead or unknown token, like the real API.
    A mutex keeps the bookkeeping exact under threads.
    """

    def __init__(self) -> None:
        self._mutex = threading.Lock()
        self.alive: set[str] = set()
        self.inits = 0
        self.kills = 0
        self.failed_kills = 0
        self.tokens_used: list[str] = []

    def request(
        self, method: str, url: str, headers: dict[str, str], **kwargs: Any
    ) -> FakeResponse:
        time.sleep(0.02)  # keeps every call in flight long enough to overlap
        with self._mutex:
            if url.endswith("/initSession"):
                self.inits += 1
                token = f"tk{self.inits}"
                self.alive.add(token)
                return FakeResponse(status_code=200, payload={"session_token": token})
            token = headers["Session-Token"]
            if url.endswith("/killSession"):
                self.kills += 1
                if token not in self.alive:
                    self.failed_kills += 1
                    return FakeResponse(status_code=401, payload={})
                self.alive.discard(token)
                return FakeResponse(status_code=200, payload={})
            self.tokens_used.append(token)
            if token not in self.alive:
                return FakeResponse(status_code=401, payload={"err": "invalid"})
            return FakeResponse(status_code=200, payload={"ok": True})

    def close(self) -> None:
        return None


def _make(server: _ServerSimulation) -> GLPIV1Session:
    session = GLPIV1Session(
        base_url="https://glpi.example.test/apirest.php",
        user_token="user-token",
        app_token="app-token",
    )
    session._http = cast(httpx.Client, server)  # type: ignore[assignment]
    return session


def _adopt(session: GLPIV1Session, server: _ServerSimulation, *, age: timedelta) -> None:
    """Give ``session`` a live token acquired ``age`` ago."""

    server.inits += 1
    token = f"tk{server.inits}"
    server.alive.add(token)
    session._session_token = token
    session._session_started_at = datetime.now(tz=UTC) - age


def _burst(session: GLPIV1Session) -> list[object]:
    """Run ``_THREADS`` requests that all start at the same moment."""

    barrier = threading.Barrier(_THREADS)

    def _one() -> object:
        barrier.wait(timeout=10)
        return session.request_json("GET", "Ticket")

    with ThreadPoolExecutor(max_workers=_THREADS) as pool:
        futures = [pool.submit(cast(Callable[[], object], _one)) for _ in range(_THREADS)]
        return [future.result(timeout=30) for future in futures]


def test_concurrent_requests_on_a_stale_session_renew_it_once() -> None:
    server = _ServerSimulation()
    session = _make(server)
    _adopt(session, server, age=timedelta(hours=1))

    results = _burst(session)

    assert results == [{"ok": True}] * _THREADS
    assert server.kills == 1
    assert server.failed_kills == 0
    assert server.inits == 2  # the adopted session and its single replacement
    assert server.tokens_used == ["tk2"] * _THREADS
    assert server.alive == {"tk2"}  # nothing leaked on the server


def test_concurrent_first_use_opens_one_session() -> None:
    server = _ServerSimulation()
    session = _make(server)

    results = _burst(session)

    assert results == [{"ok": True}] * _THREADS
    assert server.inits == 1
    assert server.kills == 0
    assert server.tokens_used == ["tk1"] * _THREADS


def test_concurrent_rejections_of_one_token_renew_it_once() -> None:
    server = _ServerSimulation()
    session = _make(server)
    _adopt(session, server, age=timedelta(seconds=1))
    server.alive.clear()  # the server dropped the session behind the client's back

    results = _burst(session)

    assert results == [{"ok": True}] * _THREADS
    assert server.inits == 2
    assert server.kills == 1  # one best-effort kill of the dead token
    assert server.alive == {"tk2"}
    assert server.tokens_used.count("tk2") == _THREADS


def test_close_after_a_renewal_kills_only_the_current_session() -> None:
    server = _ServerSimulation()
    session = _make(server)
    _adopt(session, server, age=timedelta(hours=1))
    _burst(session)

    session.close()

    assert server.alive == set()
    assert server.kills == 2
    assert session._session_token is None
