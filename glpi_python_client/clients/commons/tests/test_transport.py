"""Unit tests for the synchronous GLPI transport mixin.

The tests exercise the core dispatch path — ``_ensure_token``,
``_send_request``, ``_execute_request``, and the four HTTP-verb helpers —
using a real :class:`GlpiClient` with its session and auth stubbed out so no
real network call is made.
"""

from __future__ import annotations

from typing import Any

import pytest

from glpi_python_client.testing.utils import FakeResponse, make_client


@pytest.fixture
def client():  # type: ignore[no-untyped-def]
    """Return a test client with auth and send_request pre-stubbed."""

    c = make_client()
    # Inject a ready access token and make ensure_token a no-op so the
    # transport helpers can be called without network access.
    c._auth.access_token = "test-token"
    c._auth.ensure_token = lambda: None  # type: ignore[method-assign]
    # Stub _send_request at the seam level so _execute_request exercises the
    # real header-building logic while returning a controlled response.
    c._send_request = lambda method, url, **kw: FakeResponse(  # type: ignore[method-assign]
        status_code=200, payload={"id": 1}
    )
    yield c
    c.close()


def test_ensure_token_calls_auth_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_ensure_token`` invokes ``_auth.ensure_token`` on an open client."""

    c = make_client()
    called: list[bool] = []
    c._auth.ensure_token = lambda: called.append(True)  # type: ignore[method-assign]
    c._ensure_token()
    assert called
    c.close()


def test_send_request_dispatches_through_session_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_send_request`` routes through ``session.request`` with an upper verb.

    The verb is passed as a *value* to ``request`` rather than being looked
    up as a per-verb attribute: that is the one call shape ``requests`` and
    ``httpx`` share, so the transport swap does not have to reason about
    dynamic attribute lookup.
    """

    c = make_client()
    fake = FakeResponse(status_code=200, payload={})
    seen: dict[str, object] = {}

    def _request(method: str, url: str, **kw: object) -> FakeResponse:
        seen.update({"method": method, "url": url, "kw": kw})
        return fake

    monkeypatch.setattr(c._session, "request", _request)
    result = c._send_request(
        "get", "https://glpi.example.test/api.php/v2/test", timeout=30
    )
    assert result is fake
    assert seen["method"] == "GET"
    assert seen["url"] == "https://glpi.example.test/api.php/v2/test"
    assert seen["kw"] == {"timeout": 30}
    c.close()


def test_send_request_does_not_use_per_verb_attributes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stubbing only ``session.get`` must no longer intercept a GET.

    This pins the seam: if dispatch ever regresses to
    ``getattr(session, verb)`` this test fails, because the per-verb
    attribute would be used again.
    """

    c = make_client()
    sentinel = FakeResponse(status_code=418, payload={})
    monkeypatch.setattr(c._session, "get", lambda url, **kw: sentinel)
    captured: dict[str, object] = {}

    def _request(method: str, url: str, **kw: object) -> FakeResponse:
        captured["used"] = True
        return FakeResponse(status_code=200, payload={})

    monkeypatch.setattr(c._session, "request", _request)
    result = c._send_request("get", "https://glpi.example.test/api.php/v2/test")
    assert captured.get("used") is True
    assert result is not sentinel
    c.close()


def test_execute_request_get_builds_params(client: Any) -> None:
    """``_execute_request`` places query params on GET requests."""

    captured: dict[str, Any] = {}

    def _capture(method: str, url: str, **kw: Any) -> FakeResponse:
        captured.update({"method": method, "url": url, "kw": kw})
        return FakeResponse(status_code=200, payload={})

    client._send_request = _capture  # type: ignore[method-assign]
    client._execute_request(
        method="get",
        endpoint="Assistance/Ticket",
        success_statuses=(200,),
        params={"range": "0-49"},
    )
    assert captured["method"] == "get"
    assert "Assistance/Ticket" in captured["url"]
    assert "params" in captured["kw"]


def test_execute_request_post_builds_json_body(client: Any) -> None:
    """``_execute_request`` places the body in ``json`` for non-GET verbs."""

    captured: dict[str, Any] = {}

    def _capture(method: str, url: str, **kw: Any) -> FakeResponse:
        captured.update({"method": method, "kw": kw})
        return FakeResponse(status_code=201, payload={})

    client._send_request = _capture  # type: ignore[method-assign]
    client._execute_request(
        method="post",
        endpoint="Assistance/Ticket",
        success_statuses=(201,),
        json_body={"name": "t"},
        include_content_type=True,
    )
    assert captured["method"] == "post"
    assert captured["kw"].get("json") == {"name": "t"}


def test_get_request_returns_response(client: Any) -> None:
    """``_get_request`` dispatches via ``_execute_request`` and returns the response."""

    resp = client._get_request("Assistance/Ticket")
    assert resp.status_code == 200


def test_post_request_returns_response(client: Any) -> None:
    """``_post_request`` dispatches and returns the response."""

    client._send_request = lambda method, url, **kw: FakeResponse(  # type: ignore[method-assign]
        status_code=201, payload={"id": 99}
    )
    resp = client._post_request("Assistance/Ticket", json_body={"name": "t"})
    assert resp.status_code == 201


def test_update_request_returns_response(client: Any) -> None:
    """``_update_request`` dispatches and returns the response."""

    client._send_request = lambda method, url, **kw: FakeResponse(  # type: ignore[method-assign]
        status_code=200, payload={}
    )
    resp = client._update_request("Assistance/Ticket/1", json_body={"name": "u"})
    assert resp.status_code == 200


def test_delete_request_returns_response(client: Any) -> None:
    """``_delete_request`` dispatches and returns the response."""

    client._send_request = lambda method, url, **kw: FakeResponse(  # type: ignore[method-assign]
        status_code=204, payload={}
    )
    resp = client._delete_request("Assistance/Ticket/1")
    assert resp.status_code == 204
