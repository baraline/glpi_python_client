from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest

from glpi_python_client import GlpiClient, GlpiTeamMember
from glpi_python_client.testing.utils import FakeResponse


def _empty_response() -> FakeResponse:
    return FakeResponse(status_code=204, payload={}, text="", content=b"")


def test_client_normalizes_glpi_api_url_and_headers(
    client_factory: Callable[..., GlpiClient],
) -> None:
    client = client_factory(glpi_entity=2, glpi_profile=3, entity_recursive=True)
    try:
        client._auth.access_token = "token"

        headers = client._get_headers()

        assert client.glpi_api_url == "https://glpi.example.test/api.php"
        assert headers["Authorization"] == "Bearer token"
        assert headers["GLPI-Entity"] == "2"
        assert headers["GLPI-Profile"] == "3"
        assert headers["GLPI-Entity-Recursive"] == "true"
    finally:
        client.close()


def test_delete_ticket_omits_json_content_type_without_payload(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()
    requests: list[dict[str, object]] = []

    def ensure_token() -> None:
        client._auth.access_token = "token"

    def delete(url: str, **kwargs: object) -> FakeResponse:
        requests.append({"url": url, **kwargs})
        return _empty_response()

    monkeypatch.setattr(client._auth, "ensure_token", ensure_token)
    monkeypatch.setattr(client._session, "delete", delete)
    try:
        client.delete_ticket("321")

        headers = cast(dict[str, str], requests[0]["headers"])
        assert requests[0]["url"] == (
            "https://glpi.example.test/api.php/Assistance/Ticket/321"
        )
        assert "Content-Type" not in headers
        assert requests[0]["json"] is None
    finally:
        client.close()


def test_remove_team_member_keeps_json_content_type_with_payload(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()
    requests: list[dict[str, object]] = []

    def ensure_token() -> None:
        client._auth.access_token = "token"

    def delete(url: str, **kwargs: object) -> FakeResponse:
        requests.append({"url": url, **kwargs})
        return _empty_response()

    monkeypatch.setattr(client._auth, "ensure_token", ensure_token)
    monkeypatch.setattr(client._session, "delete", delete)
    try:
        client.remove_team_member(
            "321",
            GlpiTeamMember(member_type="User", member_id=99, role="1"),
        )

        headers = cast(dict[str, str], requests[0]["headers"])
        assert headers["Content-Type"] == "application/json"
        assert requests[0]["json"] == {"type": "User", "id": 99, "role": "1"}
    finally:
        client.close()
