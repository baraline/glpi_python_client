from __future__ import annotations

from collections.abc import Callable

import pytest

from glpi_python_client import GlpiClient, GlpiTeamMember
from glpi_python_client.testing.utils import FakeResponse


def _empty_response() -> FakeResponse:
    return FakeResponse(status_code=204, payload={}, text="", content=b"")


def test_add_team_member_returns_none(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()

    def fake_post_request(
        endpoint: str,
        payload: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> FakeResponse:
        assert endpoint == "Assistance/Ticket/321/TeamMember"
        assert skip_entity is False
        assert payload == {"type": "User", "id": 99, "role": "1"}
        return FakeResponse()

    monkeypatch.setattr(client, "_post_request", fake_post_request)
    try:
        client.add_team_member(
            "321",
            GlpiTeamMember(member_type="User", member_id=99, role="1"),
        )
    finally:
        client.close()


def test_remove_team_member_returns_none(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()

    def fake_delete_request(
        endpoint: str,
        payload: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> FakeResponse:
        assert endpoint == "Assistance/Ticket/321/TeamMember"
        assert payload == {"type": "User", "id": 99, "role": "1"}
        assert skip_entity is False
        return _empty_response()

    monkeypatch.setattr(client, "_delete_request", fake_delete_request)
    try:
        client.remove_team_member(
            321,
            GlpiTeamMember(member_type="User", member_id=99, role="1"),
        )
    finally:
        client.close()
