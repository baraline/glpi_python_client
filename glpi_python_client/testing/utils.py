"""Reusable test utility builders for glpi_python_client.

This module keeps fake responses and representative payload builders in one
place so unit tests can share realistic fixtures without repeating setup.
"""

from __future__ import annotations

from typing import Any

from glpi_python_client import AsyncGlpiClient, GlpiClient

#: Base constructor keywords shared by every in-memory test client.
#:
#: Exposed so the per-tree ``_testing`` twins can build a client for their
#: own surface without duplicating the configuration, and so downstream
#: suites can override one field without restating the rest.
DEFAULT_CLIENT_CONFIG: dict[str, object] = {
    "glpi_api_url": "https://glpi.example.test/api.php/",
    "client_id": "client-id",
    "client_secret": "client-secret",
    "username": "api-user",
    "password": "api-password",
    "server_timezone": "Europe/Paris",
}


class FakeResponse:
    """Small HTTP-response stand-in for unit tests.

    The fake object implements only the attributes and ``json()`` behavior used
    by the package's tests. It is duck-typed rather than a subclass of the
    transport's response class, so it survived the move from ``requests`` to
    ``httpx`` unchanged: the library reads the reason phrase through
    :func:`~glpi_python_client._async.clients.commons._http.response_reason`, which
    accepts either the ``reason`` spelling used here or the ``reason_phrase``
    spelling ``httpx`` uses.
    """

    def __init__(
        self,
        status_code: int = 201,
        payload: object | None = None,
        *,
        headers: dict[str, str] | None = None,
        text: str | None = None,
        content: bytes | None = None,
        reason: str = "",
        url: str = "https://glpi.example.test/api.php/fake",
    ) -> None:
        self.status_code = status_code
        self._payload = {"id": 321} if payload is None else payload
        self.headers = headers or {}
        self.text = str(self._payload) if text is None else text
        self.content = self.text.encode() if content is None else content
        self.reason = reason
        self.url = url

    def json(self) -> Any:
        return self._payload


class SearchResponse(FakeResponse):
    """Fake GLPI list or search response used by tests.

    This specialization mainly exists to make test intent clearer at call
    sites.
    """

    def __init__(
        self,
        payload: list[dict[str, Any]],
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, payload=payload, headers=headers)


class TicketResponse(FakeResponse):
    """Fake GLPI single-ticket response used by tests.

    The subclass documents that the payload shape represents one ticket record
    rather than a list response.
    """

    def __init__(
        self,
        payload: dict[str, Any],
        *,
        status_code: int = 200,
    ) -> None:
        super().__init__(status_code=status_code, payload=payload)


class TokenResponse(FakeResponse):
    """Fake OAuth token response used by tests.

    By default it returns a minimal successful token payload suitable for token
    acquisition and refresh tests.
    """

    def __init__(
        self,
        status_code: int = 200,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            payload=payload or {"access_token": "token", "expires_in": 3600},
        )


def make_client(**overrides: object) -> GlpiClient:
    """Return a synchronous test client configured with sensible defaults.

    Callers can override any constructor keyword while reusing the shared base
    configuration needed by most tests.
    """

    config = dict(DEFAULT_CLIENT_CONFIG)
    config.update(overrides)
    return GlpiClient(**config)  # type: ignore[arg-type]


def make_async_client(**overrides: object) -> AsyncGlpiClient:
    """Return an asynchronous test client configured with sensible defaults.

    The helper mirrors :func:`make_client` but instantiates the
    :class:`AsyncGlpiClient` so tests can exercise the async public
    surface (and its bridge) without duplicating the base configuration.
    """

    config = dict(DEFAULT_CLIENT_CONFIG)
    config.update(overrides)
    return AsyncGlpiClient(**config)  # type: ignore[arg-type]
