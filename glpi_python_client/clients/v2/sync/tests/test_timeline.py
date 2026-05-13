from __future__ import annotations

from collections.abc import Callable

import pytest

from glpi_python_client import GlpiClient, GlpiFollowup
from glpi_python_client.testing.utils import FakeResponse


def _empty_response() -> FakeResponse:
    return FakeResponse(status_code=204, payload={}, text="", content=b"")


def test_create_followup_accepts_followup_id_response_key(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()

    def fake_post_request(
        endpoint: str,
        payload: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> FakeResponse:
        assert endpoint == "Assistance/Ticket/321/Timeline/Followup"
        assert skip_entity is False
        assert payload == {
            "content": "<p>Followup body</p>",
            "is_private": False,
        }
        return FakeResponse(payload={"followup_id": "654"})

    monkeypatch.setattr(client, "_post_request", fake_post_request)
    try:
        created = client.create_followup(
            321,
            GlpiFollowup(content="Followup body"),
        )

        assert created == "654"
    finally:
        client.close()


@pytest.mark.parametrize(
    ("method_name", "args", "expected_endpoint"),
    [
        ("delete_followup", (321, 654), "Assistance/Ticket/321/Timeline/Followup/654"),
        ("delete_solution", (321, 987), "Assistance/Ticket/321/Timeline/Solution/987"),
    ],
)
def test_delete_timeline_operations_return_none(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    args: tuple[object, ...],
    expected_endpoint: str,
) -> None:
    client = client_factory()

    def fake_delete_request(
        endpoint: str,
        payload: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> FakeResponse:
        assert endpoint == expected_endpoint
        assert payload is None
        assert skip_entity is False
        return _empty_response()

    monkeypatch.setattr(client, "_delete_request", fake_delete_request)
    try:
        operation = getattr(client, method_name)
        operation(*args)
    finally:
        client.close()
