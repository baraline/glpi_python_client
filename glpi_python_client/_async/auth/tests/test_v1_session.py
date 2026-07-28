"""Unit tests for :class:`GLPIV1Session` covering the upload lifecycle."""

from __future__ import annotations

import json as jsonlib
from typing import Any, cast

import httpx
import pytest
from tenacity import wait_fixed

from glpi_python_client import (
    GlpiProtocolError,
    GlpiServerError,
    GlpiTransportError,
    GlpiValidationError,
)
from glpi_python_client._async.auth._v1_session import GLPIV1Session
from glpi_python_client.testing.utils import FakeResponse

#: Every ``GLPIV1Session`` method carrying the shared network retry decorator.
_RETRIED_METHODS = (
    "_init_session",
    "request_json",
    "upload_document",
)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop the 3s fixed wait so retry tests stay instant.

    Each decorated method's own ``Retrying`` object is patched directly.
    Patching ``tenacity.nap.time.sleep`` would work today but silently stops
    working on the async path, so it is deliberately not used here.
    """

    for name in _RETRIED_METHODS:
        monkeypatch.setattr(getattr(GLPIV1Session, name).retry, "wait", wait_fixed(0))


class _FakeV1Http:
    """In-memory HTTP client stand-in capturing every call."""

    def __init__(self, responses: dict[str, list[FakeResponse]]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []
        self.closed = False
        self.verify = True

    def _next(self, key: str) -> FakeResponse:
        return self._responses[key].pop(0)

    async def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        timeout: int = 30,
        **kwargs: Any,
    ) -> FakeResponse:
        """Verb-agnostic entry point mirroring the real dispatch.

        ``GLPIV1Session`` routes authenticated calls through
        ``session.request(method, ...)`` rather than a per-verb attribute,
        because that is the one call shape every transport agrees on.
        This dispatches back to the per-verb handlers so their recorded
        call shapes stay identical.
        """

        verb = method.upper()
        handler = {
            "GET": self.get,
            "POST": self.post,
            "PUT": self.put,
            "DELETE": self.delete,
        }.get(verb)
        if handler is None:
            raise AssertionError(f"unexpected verb {verb!r} in fake v1 session")
        return handler(url, headers=headers, timeout=timeout, **kwargs)

    def get(
        self,
        url: str,
        headers: dict[str, str],
        timeout: int,
        **kwargs: Any,
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": "GET",
                "url": url,
                "headers": headers,
                "timeout": timeout,
                **kwargs,
            }
        )
        if url.endswith("/initSession"):
            return self._next("init")
        if url.endswith("/killSession"):
            return self._next("kill")
        return self._next("json")

    def post(
        self,
        url: str,
        headers: dict[str, str],
        timeout: int,
        files: list[Any] | None = None,
        **kwargs: Any,
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": "POST",
                "url": url,
                "headers": headers,
                "files": files,
                "timeout": timeout,
                **kwargs,
            }
        )
        if files is not None:
            return self._next("upload")
        return self._next("json")

    def put(
        self,
        url: str,
        headers: dict[str, str],
        timeout: int,
        **kwargs: Any,
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": "PUT",
                "url": url,
                "headers": headers,
                "timeout": timeout,
                **kwargs,
            }
        )
        return self._next("json")

    def delete(
        self,
        url: str,
        headers: dict[str, str],
        timeout: int,
        **kwargs: Any,
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": "DELETE",
                "url": url,
                "headers": headers,
                "timeout": timeout,
                **kwargs,
            }
        )
        return self._next("json")

    async def aclose(self) -> None:
        self.closed = True


def _make(http: _FakeV1Http) -> GLPIV1Session:
    """Build a ``GLPIV1Session`` whose HTTP layer is ``http``."""

    session = GLPIV1Session(
        base_url="https://glpi.example.test/apirest.php/",
        user_token="user-token",
        app_token="app-token",
        verify_ssl=True,
    )
    session._http = cast(httpx.AsyncClient, http)  # type: ignore[assignment]
    return session


def test_v1_session_rejects_bad_refresh_interval() -> None:
    """Constructor enforces a positive refresh interval.

    ``GlpiValidationError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working.
    """

    with pytest.raises(GlpiValidationError) as excinfo:
        GLPIV1Session(
            base_url="https://glpi.example.test/apirest.php",
            user_token="u",
            app_token="a",
            session_refresh_interval_seconds=0,
        )
    assert isinstance(excinfo.value, ValueError)


async def test_v1_upload_acquires_session_then_posts() -> None:
    """The first upload triggers ``initSession`` then the multipart POST."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "upload": [FakeResponse(status_code=201, payload={"id": 7})],
            "kill": [FakeResponse(status_code=200, payload={})],
        }
    )
    session = _make(http)

    result = await session.upload_document(
        "a.txt",
        b"abc",
        "text/plain",
        document_name="A",
        ticket_id=3,
        entity_id=2,
    )
    assert result == {"id": 7}

    init_call = http.calls[0]
    assert init_call["url"].endswith("/initSession")

    upload_call = http.calls[1]
    assert upload_call["url"].endswith("/Document")
    manifest_part = upload_call["files"][0]
    payload = jsonlib.loads(manifest_part[1][1])
    assert payload == {
        "input": {
            "name": "A",
            "_filename": ["a.txt"],
            "entities_id": 2,
            "itemtype": "Ticket",
            "items_id": 3,
            "tickets_id": 3,
        }
    }


async def test_v1_upload_renews_session_on_401() -> None:
    """An auth-failure response triggers one renew + retry path."""

    http = _FakeV1Http(
        responses={
            "init": [
                FakeResponse(status_code=200, payload={"session_token": "tk1"}),
                FakeResponse(status_code=200, payload={"session_token": "tk2"}),
            ],
            "kill": [FakeResponse(status_code=200, payload={})],
            "upload": [
                FakeResponse(status_code=401, payload={"err": "expired"}),
                FakeResponse(status_code=200, payload={"id": 9}),
            ],
        }
    )
    session = _make(http)

    result = await session.upload_document("a.txt", b"x", "text/plain")
    assert result == {"id": 9}
    methods = [c["method"] + " " + c["url"].rsplit("/", 1)[-1] for c in http.calls]
    # init -> upload(401) -> kill -> init -> upload(200)
    assert methods == [
        "GET initSession",
        "POST Document",
        "GET killSession",
        "GET initSession",
        "POST Document",
    ]


async def test_v1_upload_raises_on_5xx_after_retries() -> None:
    """5xx upload responses are retried 3x and surface as ``GlpiServerError``."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "upload": [FakeResponse(status_code=500, payload={"err": "boom"})] * 3,
            "kill": [FakeResponse(status_code=200, payload={})],
        }
    )
    session = _make(http)
    with pytest.raises(GlpiServerError) as excinfo:
        await session.upload_document("a.txt", b"x", "text/plain")
    assert excinfo.value.status_code == 500
    # The retry predicate must retry GlpiServerError, not just RequestException:
    # pin the attempt count so a predicate regression fails loudly instead of
    # silently dropping to 1 attempt.
    upload_calls = [c for c in http.calls if c["url"].endswith("/Document")]
    assert len(upload_calls) == 3


async def test_v1_upload_raises_on_4xx_without_retry() -> None:
    """Non-5xx non-success upload responses raise ``ValueError`` without retry."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "upload": [FakeResponse(status_code=400, payload={"err": "bad"})],
            "kill": [FakeResponse(status_code=200, payload={})],
        }
    )
    session = _make(http)
    with pytest.raises(ValueError, match="document upload failed"):
        await session.upload_document("a.txt", b"x", "text/plain")
    # A single attempt was performed (init + one upload).
    upload_calls = [c for c in http.calls if c["url"].endswith("/Document")]
    assert len(upload_calls) == 1


async def test_v1_upload_raises_on_unexpected_payload() -> None:
    """A non-mapping JSON payload raises ``GlpiProtocolError`` without retry.

    ``GlpiProtocolError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working.
    """

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "upload": [FakeResponse(status_code=200, payload=["unexpected"])],
            "kill": [FakeResponse(status_code=200, payload={})],
        }
    )
    session = _make(http)
    with pytest.raises(GlpiProtocolError, match="unexpected payload") as excinfo:
        await session.upload_document("a.txt", b"x", "text/plain")
    assert isinstance(excinfo.value, ValueError)


async def test_v1_init_raises_on_5xx_after_retries() -> None:
    """5xx ``initSession`` responses are retried 3x and raise ``GlpiServerError``."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=500, payload={"err": "boom"})] * 3,
        }
    )
    session = _make(http)
    with pytest.raises(GlpiServerError) as excinfo:
        await session._init_session()
    assert excinfo.value.status_code == 500
    init_calls = [c for c in http.calls if c["url"].endswith("/initSession")]
    assert len(init_calls) == 3


async def test_v1_init_raises_on_4xx_without_retry() -> None:
    """Non-5xx ``initSession`` responses raise ``ValueError`` immediately."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=401, payload={"err": "denied"})],
        }
    )
    session = _make(http)
    with pytest.raises(ValueError, match="initSession failed"):
        await session._init_session()


async def test_v1_init_raises_when_token_missing() -> None:
    """``initSession`` returning no token raises ``GlpiProtocolError`` without retry.

    ``GlpiProtocolError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working.
    """

    http = _FakeV1Http(
        responses={"init": [FakeResponse(status_code=200, payload={})]},
    )
    session = _make(http)
    with pytest.raises(GlpiProtocolError, match="no session_token") as excinfo:
        await session._init_session()
    assert isinstance(excinfo.value, ValueError)


async def test_v1_close_kills_session_and_closes_http() -> None:
    """``close`` kills any active session and closes the HTTP layer."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "kill": [FakeResponse(status_code=200, payload={})],
        }
    )
    session = _make(http)
    await session._init_session()
    await session.close()
    assert http.closed is True
    kills = [c for c in http.calls if c["url"].endswith("/killSession")]
    assert len(kills) == 1


async def test_v1_close_tolerates_kill_failure() -> None:
    """A kill-session failure is logged but does not propagate."""

    class _BoomHttp(_FakeV1Http):
        def get(self, url: str, headers: dict[str, str], timeout: int) -> FakeResponse:
            if url.endswith("/killSession"):
                raise httpx.RequestError("boom")
            return super().get(url, headers, timeout)

    http = _BoomHttp(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
        }
    )
    session = _make(http)
    await session._init_session()
    await session.close()  # must not raise
    assert http.closed is True


async def test_request_json_sends_body_and_returns_parsed_payload() -> None:
    """``request_json`` serialises the body and decodes the JSON response."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "json": [FakeResponse(status_code=200, payload={"ok": True})],
            "kill": [FakeResponse(status_code=200, payload={})],
        }
    )
    session = _make(http)
    result = await session.request_json(
        "POST",
        "PluginFieldsContainer",
        json_body={"input": {"name": "x"}},
    )
    assert result == {"ok": True}
    post_call = next(call for call in http.calls if call["method"] == "POST")
    assert post_call["url"].endswith("/PluginFieldsContainer")
    assert post_call["content"] == jsonlib.dumps({"input": {"name": "x"}})
    assert post_call["headers"]["Content-Type"] == "application/json"


async def test_request_json_supports_get_with_params() -> None:
    """``request_json`` forwards query params on GET calls."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "json": [FakeResponse(status_code=200, payload=[{"id": 1}])],
        }
    )
    session = _make(http)
    out = await session.request_json(
        "GET", "PluginFieldsContainer", params={"range": "0-1"}
    )
    assert out == [{"id": 1}]
    get_call = next(
        call for call in http.calls if call["url"].endswith("/PluginFieldsContainer")
    )
    assert get_call["params"] == {"range": "0-1"}


async def test_request_json_returns_empty_dict_on_empty_body() -> None:
    """An empty response body decodes as an empty dict instead of raising."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "json": [FakeResponse(status_code=204, payload={}, content=b"")],
        }
    )
    session = _make(http)
    assert await session.request_json("DELETE", "Some/Resource/1") == {}


async def test_request_json_raises_on_4xx_without_retry() -> None:
    """Non-5xx non-success statuses raise ``ValueError`` without retry."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "json": [FakeResponse(status_code=404, payload={"err": "missing"})],
        }
    )
    session = _make(http)
    with pytest.raises(ValueError, match="failed"):
        await session.request_json("GET", "PluginFieldsContainer")


async def test_request_json_retries_on_5xx() -> None:
    """5xx responses are retried 3x and surface as ``GlpiServerError``."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "json": [FakeResponse(status_code=500, payload={"err": "boom"})] * 3,
        }
    )
    session = _make(http)
    with pytest.raises(GlpiServerError) as excinfo:
        await session.request_json("GET", "PluginFieldsContainer")
    assert excinfo.value.status_code == 500
    json_calls = [c for c in http.calls if c["url"].endswith("/PluginFieldsContainer")]
    assert len(json_calls) == 3


async def test_request_json_retries_on_network_error() -> None:
    """Network faults during ``request_json`` are retried 3x, not swallowed.

    Pins the ``GlpiTransportError`` member of the v1 retry predicate
    (``_RETRY_ON_NETWORK_ERRORS`` in ``_v1_session.py``): the 5xx tests above
    only exercise the ``GlpiServerError`` member. Without this test a future
    edit that narrows the predicate to drop ``GlpiTransportError``
    would silently
    drop v1 network retries from 3 attempts to 1 while every committed test
    stayed green.
    """

    class _FlakyHttp(_FakeV1Http):
        def get(
            self,
            url: str,
            headers: dict[str, str],
            timeout: int,
            **kwargs: Any,
        ) -> FakeResponse:
            if url.endswith("/PluginFieldsContainer"):
                self.calls.append(
                    {
                        "method": "GET",
                        "url": url,
                        "headers": headers,
                        "timeout": timeout,
                        **kwargs,
                    }
                )
                raise httpx.ConnectError("network down")
            return super().get(url, headers, timeout, **kwargs)

    http = _FlakyHttp(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
        }
    )
    session = _make(http)
    with pytest.raises(GlpiTransportError):
        await session.request_json("GET", "PluginFieldsContainer")
    json_calls = [c for c in http.calls if c["url"].endswith("/PluginFieldsContainer")]
    assert len(json_calls) == 3


async def test_session_token_invalid_marker_triggers_renew() -> None:
    """An ``ERROR_SESSION_TOKEN_INVALID`` body marker counts as an auth failure."""

    body_text = "ERROR_SESSION_TOKEN_INVALID"
    http = _FakeV1Http(
        responses={
            "init": [
                FakeResponse(status_code=200, payload={"session_token": "tk1"}),
                FakeResponse(status_code=200, payload={"session_token": "tk2"}),
            ],
            "kill": [FakeResponse(status_code=200, payload={})],
            "upload": [
                FakeResponse(status_code=200, payload={"id": 1}, text=body_text),
                FakeResponse(status_code=200, payload={"id": 2}),
            ],
        }
    )
    session = _make(http)

    result = await session.upload_document("a.txt", b"x", "text/plain")
    assert result == {"id": 2}
