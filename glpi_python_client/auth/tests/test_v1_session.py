"""Unit tests for :class:`GLPIV1Session` covering the upload lifecycle."""

from __future__ import annotations

import json as jsonlib
from typing import Any, cast

import pytest
import requests

from glpi_python_client import GlpiServerError
from glpi_python_client.auth._v1_session import GLPIV1Session
from glpi_python_client.testing.utils import FakeResponse


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable tenacity wait between retry attempts to keep tests fast."""

    monkeypatch.setattr("tenacity.nap.time.sleep", lambda _seconds: None)


class _FakeV1Http:
    """In-memory ``requests.Session`` stand-in capturing every call."""

    def __init__(self, responses: dict[str, list[FakeResponse]]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []
        self.closed = False
        self.verify = True

    def _next(self, key: str) -> FakeResponse:
        return self._responses[key].pop(0)

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

    def close(self) -> None:
        self.closed = True


def _make(http: _FakeV1Http) -> GLPIV1Session:
    """Build a ``GLPIV1Session`` whose HTTP layer is ``http``."""

    session = GLPIV1Session(
        base_url="https://glpi.example.test/apirest.php/",
        user_token="user-token",
        app_token="app-token",
        verify_ssl=True,
    )
    session._http = cast(requests.Session, http)  # type: ignore[assignment]
    return session


def test_v1_session_rejects_bad_refresh_interval() -> None:
    """Constructor enforces a positive refresh interval."""

    with pytest.raises(ValueError):
        GLPIV1Session(
            base_url="https://glpi.example.test/apirest.php",
            user_token="u",
            app_token="a",
            session_refresh_interval_seconds=0,
        )


def test_v1_upload_acquires_session_then_posts() -> None:
    """The first upload triggers ``initSession`` then the multipart POST."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "upload": [FakeResponse(status_code=201, payload={"id": 7})],
            "kill": [FakeResponse(status_code=200, payload={})],
        }
    )
    session = _make(http)

    result = session.upload_document(
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


def test_v1_upload_renews_session_on_401() -> None:
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

    result = session.upload_document("a.txt", b"x", "text/plain")
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


def test_v1_upload_raises_on_5xx_after_retries() -> None:
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
        session.upload_document("a.txt", b"x", "text/plain")
    assert excinfo.value.status_code == 500
    # The retry predicate must retry GlpiServerError, not just RequestException:
    # pin the attempt count so a predicate regression fails loudly instead of
    # silently dropping to 1 attempt.
    upload_calls = [c for c in http.calls if c["url"].endswith("/Document")]
    assert len(upload_calls) == 3


def test_v1_upload_raises_on_4xx_without_retry() -> None:
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
        session.upload_document("a.txt", b"x", "text/plain")
    # A single attempt was performed (init + one upload).
    upload_calls = [c for c in http.calls if c["url"].endswith("/Document")]
    assert len(upload_calls) == 1


def test_v1_upload_raises_on_unexpected_payload() -> None:
    """A non-mapping JSON payload raises ``ValueError`` without retry."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "upload": [FakeResponse(status_code=200, payload=["unexpected"])],
            "kill": [FakeResponse(status_code=200, payload={})],
        }
    )
    session = _make(http)
    with pytest.raises(ValueError, match="unexpected payload"):
        session.upload_document("a.txt", b"x", "text/plain")


def test_v1_init_raises_on_5xx_after_retries() -> None:
    """5xx ``initSession`` responses are retried 3x and raise ``GlpiServerError``."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=500, payload={"err": "boom"})] * 3,
        }
    )
    session = _make(http)
    with pytest.raises(GlpiServerError) as excinfo:
        session._init_session()
    assert excinfo.value.status_code == 500
    init_calls = [c for c in http.calls if c["url"].endswith("/initSession")]
    assert len(init_calls) == 3


def test_v1_init_raises_on_4xx_without_retry() -> None:
    """Non-5xx ``initSession`` responses raise ``ValueError`` immediately."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=401, payload={"err": "denied"})],
        }
    )
    session = _make(http)
    with pytest.raises(ValueError, match="initSession failed"):
        session._init_session()


def test_v1_init_raises_when_token_missing() -> None:
    """``initSession`` returning no token raises ``ValueError`` without retry."""

    http = _FakeV1Http(
        responses={"init": [FakeResponse(status_code=200, payload={})]},
    )
    session = _make(http)
    with pytest.raises(ValueError, match="no session_token"):
        session._init_session()


def test_v1_close_kills_session_and_closes_http() -> None:
    """``close`` kills any active session and closes the HTTP layer."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "kill": [FakeResponse(status_code=200, payload={})],
        }
    )
    session = _make(http)
    session._init_session()
    session.close()
    assert http.closed is True
    kills = [c for c in http.calls if c["url"].endswith("/killSession")]
    assert len(kills) == 1


def test_v1_close_tolerates_kill_failure() -> None:
    """A kill-session failure is logged but does not propagate."""

    class _BoomHttp(_FakeV1Http):
        def get(self, url: str, headers: dict[str, str], timeout: int) -> FakeResponse:
            if url.endswith("/killSession"):
                raise requests.RequestException("boom")
            return super().get(url, headers, timeout)

    http = _BoomHttp(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
        }
    )
    session = _make(http)
    session._init_session()
    session.close()  # must not raise
    assert http.closed is True


def test_request_json_sends_body_and_returns_parsed_payload() -> None:
    """``request_json`` serialises the body and decodes the JSON response."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "json": [FakeResponse(status_code=200, payload={"ok": True})],
            "kill": [FakeResponse(status_code=200, payload={})],
        }
    )
    session = _make(http)
    result = session.request_json(
        "POST",
        "PluginFieldsContainer",
        json_body={"input": {"name": "x"}},
    )
    assert result == {"ok": True}
    post_call = next(call for call in http.calls if call["method"] == "POST")
    assert post_call["url"].endswith("/PluginFieldsContainer")
    assert post_call["data"] == jsonlib.dumps({"input": {"name": "x"}})
    assert post_call["headers"]["Content-Type"] == "application/json"


def test_request_json_supports_get_with_params() -> None:
    """``request_json`` forwards query params on GET calls."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "json": [FakeResponse(status_code=200, payload=[{"id": 1}])],
        }
    )
    session = _make(http)
    out = session.request_json("GET", "PluginFieldsContainer", params={"range": "0-1"})
    assert out == [{"id": 1}]
    get_call = next(
        call for call in http.calls if call["url"].endswith("/PluginFieldsContainer")
    )
    assert get_call["params"] == {"range": "0-1"}


def test_request_json_returns_empty_dict_on_empty_body() -> None:
    """An empty response body decodes as an empty dict instead of raising."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "json": [FakeResponse(status_code=204, payload={}, content=b"")],
        }
    )
    session = _make(http)
    assert session.request_json("DELETE", "Some/Resource/1") == {}


def test_request_json_raises_on_4xx_without_retry() -> None:
    """Non-5xx non-success statuses raise ``ValueError`` without retry."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "json": [FakeResponse(status_code=404, payload={"err": "missing"})],
        }
    )
    session = _make(http)
    with pytest.raises(ValueError, match="failed"):
        session.request_json("GET", "PluginFieldsContainer")


def test_request_json_retries_on_5xx() -> None:
    """5xx responses are retried 3x and surface as ``GlpiServerError``."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "json": [FakeResponse(status_code=500, payload={"err": "boom"})] * 3,
        }
    )
    session = _make(http)
    with pytest.raises(GlpiServerError) as excinfo:
        session.request_json("GET", "PluginFieldsContainer")
    assert excinfo.value.status_code == 500
    json_calls = [c for c in http.calls if c["url"].endswith("/PluginFieldsContainer")]
    assert len(json_calls) == 3


def test_request_json_retries_on_network_error() -> None:
    """Network faults during ``request_json`` are retried 3x, not swallowed.

    Pins the ``requests.RequestException`` member of the v1 retry predicate
    (``_RETRY_ON_NETWORK_ERRORS`` in ``_v1_session.py``): the 5xx tests above
    only exercise the ``GlpiServerError`` member. Without this test a future
    edit that narrows the predicate to drop ``requests.RequestException``
    (for example when plan 3 swaps in ``GlpiTransportError``) would silently
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
                raise requests.ConnectionError("network down")
            return super().get(url, headers, timeout, **kwargs)

    http = _FlakyHttp(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
        }
    )
    session = _make(http)
    with pytest.raises(requests.ConnectionError):
        session.request_json("GET", "PluginFieldsContainer")
    json_calls = [c for c in http.calls if c["url"].endswith("/PluginFieldsContainer")]
    assert len(json_calls) == 3


def test_session_token_invalid_marker_triggers_renew() -> None:
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

    result = session.upload_document("a.txt", b"x", "text/plain")
    assert result == {"id": 2}
