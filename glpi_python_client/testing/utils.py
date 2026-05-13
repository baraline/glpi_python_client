"""Reusable test utility builders for glpi_python_client.

This module keeps fake responses and representative payload builders in one
place so unit tests can share realistic fixtures without repeating setup.
"""

from __future__ import annotations

from typing import Any

from glpi_python_client import GlpiClient

_DEFAULT_CLIENT_CONFIG: dict[str, object] = {
    "glpi_api_url": "https://glpi.example.test/api.php/",
    "client_id": "client-id",
    "client_secret": "client-secret",
    "username": "api-user",
    "password": "api-password",
}


class FakeResponse:
    """Small ``requests.Response`` stand-in for unit tests.

    The fake object implements only the attributes and ``json()`` behavior used
    by the package's tests.
    """

    def __init__(
        self,
        status_code: int = 201,
        payload: object | None = None,
        *,
        headers: dict[str, str] | None = None,
        text: str | None = None,
        content: bytes | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = {"id": "321"} if payload is None else payload
        self.headers = headers or {}
        self.text = str(self._payload) if text is None else text
        self.content = self.text.encode() if content is None else content

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
    """Return a test client configured with sensible defaults.

    Callers can override any constructor keyword while reusing the shared base
    configuration needed by most tests.
    """

    config = dict(_DEFAULT_CLIENT_CONFIG)
    config.update(overrides)
    return GlpiClient(**config)  # type: ignore[arg-type]


def make_followup_record(**overrides: object) -> dict[str, Any]:
    """Return a representative raw GLPI followup payload.

    The payload includes attachment references so content and document-link
    parsing tests can exercise both code paths.
    """

    payload: dict[str, Any] = {
        "id": 12,
        "content": (
            "<p>Hello</p>"
            '<a href="/front/document.send.php?docid=45">attachment</a>'
            '<img src="/front/document.send.php?docid=46" />'
        ),
        "users_id": 5,
        "is_private": "1",
    }
    payload.update(overrides)
    return payload


def make_ticket_record(**overrides: object) -> dict[str, Any]:
    """Return a representative raw GLPI ticket payload.

    The payload captures the common ticket fields needed by parsing and client
    behavior tests while still allowing targeted overrides.
    """

    payload: dict[str, Any] = {
        "id": 123,
        "name": "Need help",
        "content": "<p>Body with <strong>formatting</strong></p>",
        "status": {"id": 2, "name": "Processing"},
        "entity": {"id": 7, "name": "Root"},
        "location": {"id": 8, "name": "Paris"},
        "user_recipient": {"id": 9, "name": "Requester"},
    }
    payload.update(overrides)
    return payload
