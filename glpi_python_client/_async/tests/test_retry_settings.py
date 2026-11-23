"""The retry setting: ``max_retries`` and ``retry_wait_seconds``.

The default (two retries after the first attempt, 3 s apart) reproduces the
historical behaviour of three attempts in total; ``max_retries=0`` turns
retrying off for every retried call: the v2 verbs, the v1 session helpers and
the OAuth token manager.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from glpi_python_client import (
    AsyncGlpiClient,
    GlpiServerError,
    GlpiTransportError,
    GlpiValidationError,
)
from glpi_python_client._async import _retry
from glpi_python_client._async._testing import make_client
from glpi_python_client._async.auth._v1_session import GLPIV1Session
from glpi_python_client._async.auth.auth import GLPITokenManager
from glpi_python_client.testing.utils import FakeResponse

_VERBS = ("_get_request", "_post_request", "_update_request", "_delete_request")


def _stub_send(client: Any, *, status: int | None, attempts: list[int]) -> None:
    """Make every request attempt record itself, then fail as asked."""

    async def _ensure_token() -> None:
        return None

    async def _send(method: str, url: str, **kw: Any) -> FakeResponse:
        attempts.append(1)
        if status is None:
            raise GlpiTransportError("network down")
        return FakeResponse(status_code=status, payload={}, text="x", reason="r")

    client._auth.access_token = "test-token"
    client._auth.ensure_token = _ensure_token
    client._send_request = _send


@pytest.mark.parametrize("verb", _VERBS)
@pytest.mark.parametrize("status", [500, None])
async def test_disabled_retries_send_one_request(verb: str, status: int | None) -> None:
    """With ``max_retries=0`` a 5xx or a transport error costs one request."""

    client = make_client(max_retries=0)
    attempts: list[int] = []
    _stub_send(client, status=status, attempts=attempts)
    expected = GlpiServerError if status else GlpiTransportError
    try:
        with pytest.raises(expected):
            await getattr(client, verb)("Assistance/Ticket")
    finally:
        await client.close()
    assert len(attempts) == 1


@pytest.mark.parametrize("verb", _VERBS)
@pytest.mark.parametrize("status", [500, None])
async def test_default_retries_make_three_attempts(
    verb: str, status: int | None
) -> None:
    """Without the setting the same call is attempted three times."""

    client = make_client()
    attempts: list[int] = []
    _stub_send(client, status=status, attempts=attempts)
    expected = GlpiServerError if status else GlpiTransportError
    try:
        with pytest.raises(expected):
            await getattr(client, verb)("Assistance/Ticket")
    finally:
        await client.close()
    assert len(attempts) == 3


async def test_max_retries_counts_retries_after_the_first_attempt() -> None:
    client = make_client(max_retries=4)
    attempts: list[int] = []
    _stub_send(client, status=503, attempts=attempts)
    try:
        with pytest.raises(GlpiServerError):
            await client._get_request("Assistance/Ticket")
    finally:
        await client.close()
    assert len(attempts) == 5


async def test_4xx_is_still_not_retried() -> None:
    """Which errors are retried does not depend on the setting."""

    client = make_client(max_retries=5)
    attempts: list[int] = []
    _stub_send(client, status=404, attempts=attempts)
    try:
        response = await client._get_request("Assistance/Ticket")
    finally:
        await client.close()
    assert response.status_code == 404
    assert len(attempts) == 1


def _spy_on_wait(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record every wait the retry policy builds, without really waiting."""

    waits: list[float] = []
    real = _retry.wait_fixed

    def _spy(seconds: float) -> Any:
        waits.append(seconds)
        return real(0)

    monkeypatch.setattr(_retry, "wait_fixed", _spy)
    return waits


async def test_the_configured_wait_separates_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = _spy_on_wait(monkeypatch)
    client = make_client(retry_wait_seconds=7)
    _stub_send(client, status=500, attempts=[])
    try:
        with pytest.raises(GlpiServerError):
            await client._get_request("Assistance/Ticket")
    finally:
        await client.close()
    assert waits == [7]


async def test_the_default_wait_is_three_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Undo the suite-wide zero wait so the real default is what gets built.
    monkeypatch.setattr(_retry, "DEFAULT_RETRY_WAIT_SECONDS", 3.0)
    waits = _spy_on_wait(monkeypatch)
    client = make_client()
    _stub_send(client, status=500, attempts=[])
    try:
        with pytest.raises(GlpiServerError):
            await client._get_request("Assistance/Ticket")
    finally:
        await client.close()
    assert waits == [3.0]
    assert _retry.DEFAULT_MAX_RETRIES == 2


def _v1_session(handler: Any, **kwargs: Any) -> GLPIV1Session:
    session = GLPIV1Session(
        base_url="https://glpi.example.test/apirest.php",
        user_token="user-token",
        **kwargs,
    )
    session._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return session


@pytest.mark.parametrize(("retries", "expected"), [(0, 1), (None, 3)])
async def test_the_setting_reaches_a_v1_helper(
    retries: int | None, expected: int
) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/initSession"):
            return httpx.Response(200, json={"session_token": "tk"})
        return httpx.Response(500, json={})

    kwargs = {} if retries is None else {"max_retries": retries}
    session = _v1_session(handler, **kwargs)
    try:
        with pytest.raises(GlpiServerError):
            await session.request_json("GET", "/Ticket/1")
    finally:
        await session._http.aclose()
    assert len([c for c in calls if c.endswith("/Ticket/1")]) == expected


async def test_the_setting_reaches_the_v1_init_session() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(503, json={})

    session = _v1_session(handler, max_retries=0)
    try:
        with pytest.raises(GlpiServerError):
            await session._init_session()
    finally:
        await session._http.aclose()
    assert len(calls) == 1


@pytest.mark.parametrize(("retries", "expected"), [(0, 1), (None, 3)])
async def test_the_setting_reaches_the_token_manager(
    retries: int | None, expected: int
) -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503, json={})

    kwargs = {} if retries is None else {"max_retries": retries}
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    manager = GLPITokenManager(
        token_url="https://glpi.example.test/api.php/token",
        username="u",
        password="p",
        session=http,
        **kwargs,
    )
    try:
        with pytest.raises(GlpiServerError):
            await manager.ensure_token()
    finally:
        await http.aclose()
    assert len(calls) == expected


async def test_the_client_hands_the_setting_to_its_collaborators() -> None:
    client = make_client(
        max_retries=1,
        retry_wait_seconds=2,
        v1_base_url="https://glpi.example.test/apirest.php",
        v1_user_token="user-token",
    )
    try:
        assert client._max_retries == 1
        assert client._auth._max_retries == 1
        assert client._v1 is not None
        assert client._v1._max_retries == 1
        assert client._v1._retry_wait_seconds == 2
        assert client._auth._retry_wait_seconds == 2
    finally:
        await client.close()


async def test_from_env_reads_the_setting() -> None:
    client = AsyncGlpiClient.from_env(
        env={
            "GLPI_API_URL": "https://glpi.example.test/api.php/v2",
            "GLPI_CLIENT_ID": "i",
            "GLPI_CLIENT_SECRET": "s",
            "GLPI_SERVER_TIMEZONE": "Europe/Paris",
            "GLPI_MAX_RETRIES": "0",
            "GLPI_RETRY_WAIT_SECONDS": "0.5",
        }
    )
    try:
        assert client._max_retries == 0
        assert client._retry_wait_seconds == 0.5
    finally:
        await client.close()


@pytest.mark.parametrize("bad", [-1, True, 1.5, "2"])
async def test_a_bad_max_retries_is_rejected(bad: object) -> None:
    with pytest.raises(GlpiValidationError):
        make_client(max_retries=bad)


@pytest.mark.parametrize("bad", [-1, True, "3"])
async def test_a_bad_retry_wait_is_rejected(bad: object) -> None:
    with pytest.raises(GlpiValidationError):
        make_client(retry_wait_seconds=bad)
