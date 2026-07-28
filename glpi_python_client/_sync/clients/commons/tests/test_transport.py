"""Unit tests for the asynchronous GLPI transport mixin.

The tests exercise the core dispatch path -- ``_ensure_token``,
``_send_request``, ``_execute_request``, and the four HTTP-verb helpers --
using a real :class:`AsyncGlpiClient` with its session and auth stubbed out
so no real network call is made.

Retry semantics for the v2 transport are folded in here too: 5xx is retried,
4xx is not. These tests are the regression net for the retry predicate.
Getting the predicate wrong disables retries silently -- nothing raises,
nothing fails, requests simply stop being retried. See the 0.4.0 plan-1
notes.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from tenacity import wait_fixed

from glpi_python_client import (
    GlpiClient,
    GlpiError,
    GlpiServerError,
    GlpiTimeoutError,
    GlpiTransportError,
)
from glpi_python_client._sync._testing import make_client
from glpi_python_client.testing.utils import FakeResponse

_RETRIED_METHODS = (
    "_get_request",
    "_post_request",
    "_update_request",
    "_delete_request",
)


@pytest.fixture
def transport_client() -> Iterator[Any]:
    """Yield a client with auth and send_request pre-stubbed."""

    c = make_client()
    # Inject a ready access token and make ensure_token a no-op so the
    # transport helpers can be called without network access.
    c._auth.access_token = "test-token"

    def _ensure_token() -> None:
        return None

    c._auth.ensure_token = _ensure_token  # type: ignore[method-assign]

    # Stub _send_request at the seam level so _execute_request exercises the
    # real header-building logic while returning a controlled response.
    def _send(method: str, url: str, **kw: Any) -> FakeResponse:
        return FakeResponse(status_code=200, payload={"id": 1})

    c._send_request = _send  # type: ignore[method-assign]
    yield c
    c.close()


def test_ensure_token_calls_auth_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_ensure_token`` invokes ``_auth.ensure_token`` on an open client."""

    c = make_client()
    called: list[bool] = []

    def _ensure_token() -> None:
        called.append(True)

    c._auth.ensure_token = _ensure_token  # type: ignore[method-assign]
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


def test_execute_request_get_builds_params(transport_client: Any) -> None:
    """``_execute_request`` places query params on GET requests."""

    captured: dict[str, Any] = {}

    def _capture(method: str, url: str, **kw: Any) -> FakeResponse:
        captured.update({"method": method, "url": url, "kw": kw})
        return FakeResponse(status_code=200, payload={})

    transport_client._send_request = _capture  # type: ignore[method-assign]
    transport_client._execute_request(
        method="get",
        endpoint="Assistance/Ticket",
        success_statuses=(200,),
        params={"range": "0-49"},
    )
    assert captured["method"] == "get"
    assert "Assistance/Ticket" in captured["url"]
    assert "params" in captured["kw"]


def test_execute_request_post_builds_json_body(transport_client: Any) -> None:
    """``_execute_request`` places the body in ``json`` for non-GET verbs."""

    captured: dict[str, Any] = {}

    def _capture(method: str, url: str, **kw: Any) -> FakeResponse:
        captured.update({"method": method, "kw": kw})
        return FakeResponse(status_code=201, payload={})

    transport_client._send_request = _capture  # type: ignore[method-assign]
    transport_client._execute_request(
        method="post",
        endpoint="Assistance/Ticket",
        success_statuses=(201,),
        json_body={"name": "t"},
        include_content_type=True,
    )
    assert captured["method"] == "post"
    assert captured["kw"].get("json") == {"name": "t"}


def test_get_request_returns_response(transport_client: Any) -> None:
    """``_get_request`` dispatches via ``_execute_request`` and returns the response."""

    resp = transport_client._get_request("Assistance/Ticket")
    assert resp.status_code == 200


def test_post_request_returns_response(transport_client: Any) -> None:
    """``_post_request`` dispatches and returns the response."""

    def _send(method: str, url: str, **kw: Any) -> FakeResponse:
        return FakeResponse(status_code=201, payload={"id": 99})

    transport_client._send_request = _send  # type: ignore[method-assign]
    resp = transport_client._post_request(
        "Assistance/Ticket", json_body={"name": "t"}
    )
    assert resp.status_code == 201


def test_update_request_returns_response(transport_client: Any) -> None:
    """``_update_request`` dispatches and returns the response."""

    def _send(method: str, url: str, **kw: Any) -> FakeResponse:
        return FakeResponse(status_code=200, payload={})

    transport_client._send_request = _send  # type: ignore[method-assign]
    resp = transport_client._update_request(
        "Assistance/Ticket/1", json_body={"name": "u"}
    )
    assert resp.status_code == 200


def test_delete_request_returns_response(transport_client: Any) -> None:
    """``_delete_request`` dispatches and returns the response."""

    def _send(method: str, url: str, **kw: Any) -> FakeResponse:
        return FakeResponse(status_code=204, payload={})

    transport_client._send_request = _send  # type: ignore[method-assign]
    resp = transport_client._delete_request("Assistance/Ticket/1")
    assert resp.status_code == 204


# --- Retry semantics -------------------------------------------------------
#
# These tests need a client whose ``_send_request`` has *not* been
# pre-stubbed at the instance level: several of them replace
# ``_session.request`` instead, one seam lower, and rely on the real
# ``_send_request`` bound method to route through it. If ``_send_request``
# were already overridden by ``transport_client`` above, that override would
# shadow the real method and the ``_session.request`` replacement would
# never be exercised. Hence a second, lighter fixture (``retry_client``)
# rather than reusing ``transport_client``.


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop the 3s fixed wait so retry tests stay instant.

    The decorator's ``Retrying`` object is patched directly. Patching
    ``tenacity.nap.time.sleep`` would work today but silently stops working
    on the async path, so it is deliberately not used here.
    """

    for name in _RETRIED_METHODS:
        monkeypatch.setattr(getattr(GlpiClient, name).retry, "wait", wait_fixed(0))


@pytest.fixture
def retry_client() -> Iterator[Any]:
    """Return a client with auth stubbed so no token call is made."""

    c = make_client()
    c._auth.access_token = "test-token"

    def _ensure_token() -> None:
        return None

    c._auth.ensure_token = _ensure_token  # type: ignore[method-assign]
    yield c
    c.close()


@pytest.mark.parametrize("method_name", _RETRIED_METHODS)
def test_5xx_is_retried_three_times_and_reraises_server_error(
    retry_client: Any, method_name: str
) -> None:
    """A persistent 5xx costs 3 attempts and surfaces as ``GlpiServerError``.

    Parametrized across all four retried verbs (``_get_request``,
    ``_post_request``, ``_update_request``, ``_delete_request``): they share
    the same decorator, but before this test only ``_get_request``'s attempt
    count was pinned.
    """

    attempts: list[int] = []

    def _send(method: str, url: str, **kw: Any) -> FakeResponse:
        attempts.append(1)
        return FakeResponse(
            status_code=500, payload={}, text="boom", reason="Server Error"
        )

    retry_client._send_request = _send  # type: ignore[method-assign]
    with pytest.raises(GlpiServerError) as excinfo:
        getattr(retry_client, method_name)("Assistance/Ticket")

    assert len(attempts) == 3
    assert excinfo.value.status_code == 500
    assert excinfo.value.url == "https://glpi.example.test/api.php/Assistance/Ticket"


def test_persistent_5xx_does_not_surface_as_retry_error(
    retry_client: Any,
) -> None:
    """``reraise=True``: callers see the real error, never ``tenacity.RetryError``."""

    import tenacity

    def _send(method: str, url: str, **kw: Any) -> FakeResponse:
        return FakeResponse(
            status_code=503, payload={}, text="down", reason="Service Unavailable"
        )

    retry_client._send_request = _send  # type: ignore[method-assign]
    with pytest.raises(GlpiServerError) as excinfo:
        retry_client._get_request("Assistance/Ticket")
    assert not isinstance(excinfo.value, tenacity.RetryError)


@pytest.mark.parametrize("method_name", _RETRIED_METHODS)
def test_4xx_is_not_retried_by_the_transport(
    retry_client: Any, method_name: str
) -> None:
    """A 4xx is logged and returned by ``finalize_request_response``, not retried.

    Parametrized across all four retried verbs so a predicate regression
    that starts retrying 4xx on any single verb fails loudly.
    """

    attempts: list[int] = []

    def _send(method: str, url: str, **kw: Any) -> FakeResponse:
        attempts.append(1)
        return FakeResponse(status_code=404, payload={}, text="nope")

    retry_client._send_request = _send  # type: ignore[method-assign]
    response = getattr(retry_client, method_name)("Assistance/Ticket/1")

    assert len(attempts) == 1
    assert response.status_code == 404


def test_tolerant_search_still_returns_empty_on_4xx(retry_client: Any) -> None:
    """Search endpoints that pass no ``failure_message`` still swallow a 4xx.

    Guards the 7 tolerant ``_resource_list`` call sites against the 4xx raise
    being moved into ``finalize_request_response``.
    """

    def _send(method: str, url: str, **kw: Any) -> FakeResponse:
        return FakeResponse(status_code=400, payload=[], text="[]")

    retry_client._send_request = _send  # type: ignore[method-assign]
    assert retry_client.search_tickets() == []


@pytest.mark.parametrize("method_name", _RETRIED_METHODS)
def test_network_errors_are_still_retried(
    retry_client: Any, method_name: str
) -> None:
    """Real transport faults are translated and still retried three times.

    The fault is injected at ``session.request`` -- *below* the translation
    boundary -- rather than by stubbing ``_send_request``. That matters: a stub
    above the boundary would raise the HTTP library's own exception, which the
    retry predicate no longer names, so the test would pass or fail for
    reasons unrelated to the behaviour it is meant to pin. Injecting here
    exercises the real path end to end: a genuine ``httpx`` fault, translated
    into ``GlpiTransportError``, matched by the predicate, retried three
    times, and surfaced to the caller as a library error.

    Parametrized across all four retried verbs so the network-fault attempt
    count is pinned for each, not just ``_get_request``.
    """

    attempts: list[int] = []

    def _request(method: str, url: str, **kw: Any) -> FakeResponse:
        attempts.append(1)
        raise httpx.ConnectError("network down")

    retry_client._session.request = _request
    with pytest.raises(GlpiTransportError):
        getattr(retry_client, method_name)("Assistance/Ticket")

    assert len(attempts) == 3


@pytest.mark.parametrize("method_name", _RETRIED_METHODS)
def test_no_third_party_exception_reaches_the_caller(
    retry_client: Any, method_name: str
) -> None:
    """A network fault never surfaces as the HTTP library's own exception.

    The public contract is that ``GlpiError`` is sufficient to catch the
    library's failures. This pins the half of that promise which used to be
    false: transport faults escaped as third-party exceptions, forcing callers
    to import the HTTP library. If the translation is ever removed, the raw
    exception reaches the caller and this fails.
    """

    def _request(method: str, url: str, **kw: Any) -> FakeResponse:
        raise httpx.ConnectError("network down")

    retry_client._session.request = _request
    with pytest.raises(GlpiError) as excinfo:
        getattr(retry_client, method_name)("Assistance/Ticket")

    assert not isinstance(excinfo.value, httpx.HTTPError)
    # The original fault stays reachable for debugging.
    assert isinstance(excinfo.value.__cause__, httpx.ConnectError)


def test_timeouts_narrow_to_the_timeout_subclass(retry_client: Any) -> None:
    """A timeout surfaces as ``GlpiTimeoutError``, not just the base class.

    ``GlpiTimeoutError`` exists so callers can single out the "GLPI was too
    slow" case from "GLPI was unreachable". That only works if the translation
    actually inspects the fault type rather than flattening everything to the
    base class.
    """

    def _request(method: str, url: str, **kw: Any) -> FakeResponse:
        raise httpx.ConnectTimeout("too slow")

    retry_client._session.request = _request
    with pytest.raises(GlpiTimeoutError):
        retry_client._get_request("Assistance/Ticket")
