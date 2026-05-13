from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from glpi_python_client import GlpiClient, GlpiTicket
from glpi_python_client.testing.utils import (
    FakeResponse,
    SearchResponse,
    TicketResponse,
    make_ticket_record,
)


def _empty_response() -> FakeResponse:
    return FakeResponse(status_code=204, payload={}, text="", content=b"")


def test_get_ticket_record_excludes_deleted_ticket_by_default(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()

    def fake_get_request(
        endpoint: str,
        params: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> TicketResponse:
        assert endpoint == "Assistance/Ticket/123"
        assert params is None
        assert skip_entity is False
        return TicketResponse(make_ticket_record(id=123, is_deleted=1))

    monkeypatch.setattr(client, "_get_request", fake_get_request)
    try:
        with pytest.raises(ValueError, match="deleted"):
            client.get_ticket_record("123")
    finally:
        client.close()


def test_get_ticket_record_can_include_deleted_ticket(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()

    def fake_get_request(
        endpoint: str,
        params: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> TicketResponse:
        assert endpoint == "Assistance/Ticket/123"
        assert params is None
        assert skip_entity is False
        return TicketResponse(make_ticket_record(id=123, is_deleted=1))

    monkeypatch.setattr(client, "_get_request", fake_get_request)
    try:
        ticket = client.get_ticket_record("123", include_deleted_ticket=True)

        assert ticket.id == "123"
    finally:
        client.close()


def test_get_ticket_record_accepts_integer_identifier(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()

    def fake_get_request(
        endpoint: str,
        params: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> TicketResponse:
        assert endpoint == "Assistance/Ticket/123"
        assert params is None
        assert skip_entity is False
        return TicketResponse(make_ticket_record(id=123))

    monkeypatch.setattr(client, "_get_request", fake_get_request)
    try:
        ticket = client.get_ticket_record(123)

        assert ticket.id == "123"
    finally:
        client.close()


def test_create_ticket_does_not_inject_package_defaults(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()
    payload_data: dict[str, object] | None = None

    def fake_post_request(
        endpoint: str,
        payload: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> FakeResponse:
        nonlocal payload_data
        assert endpoint == "Assistance/Ticket"
        assert skip_entity is False
        assert payload is not None
        payload_data = payload
        return FakeResponse()

    monkeypatch.setattr(client, "_post_request", fake_post_request)
    try:
        created = client.create_ticket(GlpiTicket(name="Need help"))

        assert created == "321"
        assert payload_data == {"name": "Need help"}
    finally:
        client.close()


def test_create_ticket_accepts_public_extra_payload(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()
    payload_data: dict[str, object] | None = None

    def fake_post_request(
        endpoint: str,
        payload: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> FakeResponse:
        nonlocal payload_data
        assert endpoint == "Assistance/Ticket"
        assert skip_entity is False
        assert payload is not None
        payload_data = payload
        return FakeResponse()

    monkeypatch.setattr(client, "_post_request", fake_post_request)
    try:
        created = client.create_ticket(
            GlpiTicket(
                name="Need help",
                extra_payload={"_room_code": "PAR-3F-12"},
            )
        )

        assert created == "321"
        assert payload_data == {
            "name": "Need help",
            "_room_code": "PAR-3F-12",
        }
    finally:
        client.close()


def test_create_ticket_requires_name(
    client_factory: Callable[..., GlpiClient],
) -> None:
    client = client_factory()
    try:
        with pytest.raises(ValueError, match="ticket creation requires a name"):
            client.create_ticket(GlpiTicket(content="Body only"))
    finally:
        client.close()


def test_update_ticket_returns_none(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()

    def fake_update_request(
        endpoint: str,
        payload: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> FakeResponse:
        assert endpoint == "Assistance/Ticket/321"
        assert skip_entity is False
        assert payload == {"name": "Updated"}
        response = FakeResponse()
        response.status_code = 204
        response.text = ""
        response.content = b""
        return response

    monkeypatch.setattr(client, "_update_request", fake_update_request)
    try:
        client.update_ticket("321", GlpiTicket(name="Updated"))
    finally:
        client.close()


def test_delete_ticket_returns_none(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()

    def fake_delete_request(
        endpoint: str,
        payload: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> FakeResponse:
        assert endpoint == "Assistance/Ticket/321"
        assert payload is None
        assert skip_entity is False
        return _empty_response()

    monkeypatch.setattr(client, "_delete_request", fake_delete_request)
    try:
        client.delete_ticket(321)
    finally:
        client.close()


def test_search_ticket_records_returns_full_list_by_default(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()
    requests: list[dict[str, object]] = []
    responses = iter(
        [
            SearchResponse(
                [
                    make_ticket_record(id=1, name="Ticket 1"),
                    make_ticket_record(id=2, name="Ticket 2"),
                ],
                status_code=206,
                headers={"Content-Range": "0-1/3"},
            ),
            SearchResponse(
                [make_ticket_record(id=3, name="Ticket 3")],
                status_code=200,
                headers={"Content-Range": "2-2/3"},
            ),
        ]
    )

    def fake_get_request(
        endpoint: str,
        params: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> SearchResponse:
        assert endpoint == "Assistance/Ticket"
        assert skip_entity is False
        requests.append(dict(params or {}))
        return next(responses)

    monkeypatch.setattr(client, "_get_request", fake_get_request)
    try:
        tickets = client.search_ticket_records()

        assert [ticket.id for ticket in tickets] == ["1", "2", "3"]
        assert [request["start"] for request in requests] == [0, 2]
        assert all("limit" not in request for request in requests)
    finally:
        client.close()


@pytest.mark.parametrize(
    ("include_deleted_ticket", "expected_ids"),
    [(False, ["1"]), (True, ["1", "2"])],
)
def test_search_ticket_records_controls_deleted_ticket_results(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
    include_deleted_ticket: bool,
    expected_ids: list[str],
) -> None:
    client = client_factory()
    responses = iter(
        [
            SearchResponse(
                [
                    make_ticket_record(id=1, name="Ticket 1"),
                    make_ticket_record(id=2, name="Ticket 2", is_deleted=1),
                ],
                headers={"Content-Range": "0-1/2"},
            ),
        ]
    )

    def fake_get_request(
        endpoint: str,
        params: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> SearchResponse:
        assert endpoint == "Assistance/Ticket"
        assert params is not None
        assert params["start"] == 0
        assert "is_deleted" in str(params.get("fields"))
        assert skip_entity is False
        return next(responses)

    monkeypatch.setattr(client, "_get_request", fake_get_request)
    try:
        if include_deleted_ticket:
            tickets = client.search_ticket_records(include_deleted_ticket=True)
        else:
            tickets = client.search_ticket_records()

        assert [ticket.id for ticket in tickets] == expected_ids
    finally:
        client.close()


def test_search_ticket_records_returns_lazy_batches_when_requested(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()
    requests: list[dict[str, object]] = []
    responses = iter(
        [
            SearchResponse(
                [
                    make_ticket_record(id=1, name="Ticket 1"),
                    make_ticket_record(id=2, name="Ticket 2"),
                ],
                status_code=206,
                headers={"Content-Range": "0-1/3"},
            ),
            SearchResponse(
                [make_ticket_record(id=3, name="Ticket 3")],
                status_code=200,
                headers={"Content-Range": "2-2/3"},
            ),
        ]
    )

    def fake_get_request(
        endpoint: str,
        params: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> SearchResponse:
        assert endpoint == "Assistance/Ticket"
        assert skip_entity is False
        requests.append(dict(params or {}))
        return next(responses)

    monkeypatch.setattr(client, "_get_request", fake_get_request)
    try:
        batches = client.search_ticket_records(batch_size=2)

        assert requests == []
        assert [[ticket.id for ticket in batch] for batch in batches] == [
            ["1", "2"],
            ["3"],
        ]
        assert [request["start"] for request in requests] == [0, 2]
        assert [request["limit"] for request in requests] == [2, 2]
    finally:
        client.close()


def test_search_ticket_records_follows_server_default_pagination(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()
    requests: list[dict[str, object]] = []
    responses = iter(
        [
            SearchResponse(
                [
                    make_ticket_record(id=1, name="Ticket 1"),
                    make_ticket_record(id=2, name="Ticket 2"),
                ]
            ),
            SearchResponse([make_ticket_record(id=3, name="Ticket 3")]),
        ]
    )

    def fake_get_request(
        endpoint: str,
        params: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> SearchResponse:
        assert endpoint == "Assistance/Ticket"
        assert skip_entity is False
        requests.append(dict(params or {}))
        return next(responses)

    monkeypatch.setattr(client, "_get_request", fake_get_request)
    try:
        tickets = client.search_ticket_records()

        assert [ticket.id for ticket in tickets] == ["1", "2", "3"]
        assert [request["start"] for request in requests] == [0, 2]
        assert all("limit" not in request for request in requests)
    finally:
        client.close()


def test_sync_client_can_run_inside_running_event_loop(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_test() -> None:
        client = client_factory()

        def fake_get_request(
            endpoint: str,
            params: dict[str, object] | None = None,
            skip_entity: bool = False,
        ) -> SearchResponse:
            assert endpoint == "Assistance/Ticket"
            assert skip_entity is False
            assert params is not None
            return SearchResponse(
                [make_ticket_record(id=1, name="Ticket 1")],
                headers={"Content-Range": "0-0/1"},
            )

        monkeypatch.setattr(client, "_get_request", fake_get_request)
        try:
            tickets = client.search_ticket_records()

            assert [ticket.id for ticket in tickets] == ["1"]
        finally:
            client.close()

    asyncio.run(run_test())
