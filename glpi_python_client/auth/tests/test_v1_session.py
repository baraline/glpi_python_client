"""Unit tests for :class:`GLPIV1Session` covering the upload lifecycle."""

from __future__ import annotations

import json as jsonlib
from typing import Any, cast

import pytest
import requests
import tenacity

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

    def get(self, url: str, headers: dict[str, str], timeout: int) -> FakeResponse:
        self.calls.append(
            {"method": "GET", "url": url, "headers": headers, "timeout": timeout}
        )
        if url.endswith("/initSession"):
            return self._next("init")
        if url.endswith("/killSession"):
            return self._next("kill")
        raise AssertionError(f"Unexpected GET {url}")

    def post(
        self,
        url: str,
        headers: dict[str, str],
        files: list[Any],
        timeout: int,
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": "POST",
                "url": url,
                "headers": headers,
                "files": files,
                "timeout": timeout,
            }
        )
        return self._next("upload")

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


def test_v1_upload_raises_on_non_success() -> None:
    """Non-success upload responses raise ``ValueError`` (after retries)."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "upload": [FakeResponse(status_code=500, payload={"err": "boom"})] * 3,
            "kill": [FakeResponse(status_code=200, payload={})],
        }
    )
    session = _make(http)
    with pytest.raises(tenacity.RetryError) as excinfo:
        session.upload_document("a.txt", b"x", "text/plain")
    inner = excinfo.value.last_attempt.exception()
    assert isinstance(inner, ValueError) and "document upload failed" in str(inner)


def test_v1_upload_raises_on_unexpected_payload() -> None:
    """A non-mapping JSON payload raises ``ValueError`` (after retries)."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=200, payload={"session_token": "tk"})],
            "upload": [FakeResponse(status_code=200, payload=["unexpected"])] * 3,
            "kill": [FakeResponse(status_code=200, payload={})],
        }
    )
    session = _make(http)
    with pytest.raises(tenacity.RetryError) as excinfo:
        session.upload_document("a.txt", b"x", "text/plain")
    inner = excinfo.value.last_attempt.exception()
    assert isinstance(inner, ValueError) and "unexpected payload" in str(inner)


def test_v1_init_raises_on_failure() -> None:
    """``initSession`` failure raises ``ValueError`` after retries exhaust."""

    http = _FakeV1Http(
        responses={
            "init": [FakeResponse(status_code=500, payload={"err": "boom"})] * 3,
        }
    )
    session = _make(http)
    with pytest.raises(tenacity.RetryError) as excinfo:
        session._init_session()
    inner = excinfo.value.last_attempt.exception()
    assert isinstance(inner, ValueError) and "initSession failed" in str(inner)


def test_v1_init_raises_when_token_missing() -> None:
    """``initSession`` returning no token raises ``ValueError`` after retries."""

    http = _FakeV1Http(
        responses={"init": [FakeResponse(status_code=200, payload={})] * 3},
    )
    session = _make(http)
    with pytest.raises(tenacity.RetryError) as excinfo:
        session._init_session()
    inner = excinfo.value.last_attempt.exception()
    assert isinstance(inner, ValueError) and "no session_token" in str(inner)


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
