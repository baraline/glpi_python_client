"""Retry semantics for the v2 transport: 5xx is retried, 4xx is not.

These tests are the regression net for the retry predicate. Getting the
predicate wrong disables retries silently — nothing raises, nothing fails,
requests simply stop being retried. See the 0.4.0 plan-1 notes.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
import requests
from tenacity import wait_fixed

from glpi_python_client import GlpiClient, GlpiNotFoundError, GlpiServerError
from glpi_python_client.clients.commons._http import ensure_response_status
from glpi_python_client.testing.utils import FakeResponse, make_client

_RETRIED_METHODS = (
    "_get_request",
    "_post_request",
    "_update_request",
    "_delete_request",
)


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
def client() -> Iterator[Any]:
    """Return a client with auth stubbed so no token call is made."""

    c = make_client()
    c._auth.access_token = "test-token"
    c._auth.ensure_token = lambda: None
    yield c
    c.close()


@pytest.mark.parametrize("method_name", _RETRIED_METHODS)
def test_5xx_is_retried_three_times_and_reraises_server_error(
    client: Any, method_name: str
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

    client._send_request = _send
    with pytest.raises(GlpiServerError) as excinfo:
        getattr(client, method_name)("Assistance/Ticket")

    assert len(attempts) == 3
    assert excinfo.value.status_code == 500
    assert excinfo.value.url == "https://glpi.example.test/api.php/Assistance/Ticket"


def test_persistent_5xx_does_not_surface_as_retry_error(client: Any) -> None:
    """``reraise=True``: callers see the real error, never ``tenacity.RetryError``."""

    import tenacity

    client._send_request = lambda method, url, **kw: FakeResponse(
        status_code=503, payload={}, text="down", reason="Service Unavailable"
    )
    with pytest.raises(GlpiServerError) as excinfo:
        client._get_request("Assistance/Ticket")
    assert not isinstance(excinfo.value, tenacity.RetryError)


@pytest.mark.parametrize("method_name", _RETRIED_METHODS)
def test_4xx_is_not_retried_by_the_transport(client: Any, method_name: str) -> None:
    """A 4xx is logged and returned by ``finalize_request_response``, not retried.

    Parametrized across all four retried verbs so a predicate regression
    that starts retrying 4xx on any single verb fails loudly.
    """

    attempts: list[int] = []

    def _send(method: str, url: str, **kw: Any) -> FakeResponse:
        attempts.append(1)
        return FakeResponse(status_code=404, payload={}, text="nope")

    client._send_request = _send
    response = getattr(client, method_name)("Assistance/Ticket/1")

    assert len(attempts) == 1
    assert response.status_code == 404


def test_4xx_raises_a_typed_status_error_from_ensure_response_status() -> None:
    """The 4xx raise stays in ``ensure_response_status`` and is typed."""

    response = FakeResponse(status_code=404, payload={}, text="nope")
    with pytest.raises(GlpiNotFoundError) as excinfo:
        ensure_response_status(
            response,
            success_statuses=(200, 206),
            failure_message="Failed to fetch ticket 1",
        )

    assert excinfo.value.status_code == 404
    assert isinstance(excinfo.value, ValueError)
    assert str(excinfo.value) == "Failed to fetch ticket 1: 404 nope"


def test_tolerant_search_still_returns_empty_on_4xx(client: Any) -> None:
    """Search endpoints that pass no ``failure_message`` still swallow a 4xx.

    Guards the 7 tolerant ``_resource_list`` call sites against the 4xx raise
    being moved into ``finalize_request_response``.
    """

    client._send_request = lambda method, url, **kw: FakeResponse(
        status_code=400, payload=[], text="[]"
    )
    assert client.search_tickets() == []


@pytest.mark.parametrize("method_name", _RETRIED_METHODS)
def test_network_errors_are_still_retried(client: Any, method_name: str) -> None:
    """Real ``requests`` transport faults keep their retry behaviour.

    Parametrized across all four retried verbs so the network-fault attempt
    count is pinned for each, not just ``_get_request``.
    """

    attempts: list[int] = []

    def _send(method: str, url: str, **kw: Any) -> FakeResponse:
        attempts.append(1)
        raise requests.ConnectionError("network down")

    client._send_request = _send
    with pytest.raises(requests.ConnectionError):
        getattr(client, method_name)("Assistance/Ticket")

    assert len(attempts) == 3
