from __future__ import annotations

import asyncio

import pytest

from glpi_python_client import AsyncGlpiClient, GlpiTicket
from glpi_python_client.testing.utils import (
    FakeResponse,
    SearchResponse,
    TicketResponse,
    make_ticket_record,
)


def _empty_response() -> FakeResponse:
    return FakeResponse(status_code=204, payload={}, text="", content=b"")


def test_async_get_ticket_record_can_include_deleted_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_test() -> None:
        client = AsyncGlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/",
            client_id="client-id",
            client_secret="client-secret",
        )

        async def fake_get_request(
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
            ticket = await client.get_ticket_record(
                "123",
                include_deleted_ticket=True,
            )

            assert ticket.id == "123"
        finally:
            await client.close()

    asyncio.run(run_test())


def test_async_create_ticket_accepts_public_extra_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_test() -> None:
        client = AsyncGlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/",
            client_id="client-id",
            client_secret="client-secret",
        )
        payload_data: dict[str, object] | None = None

        async def fake_post_request(
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
            created = await client.create_ticket(
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
            await client.close()

    asyncio.run(run_test())


def test_async_delete_ticket_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_test() -> None:
        client = AsyncGlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/",
            client_id="client-id",
            client_secret="client-secret",
        )

        async def fake_delete_request(
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
            await client.delete_ticket(321)
        finally:
            await client.close()

    asyncio.run(run_test())


def test_async_search_ticket_records_returns_full_list_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_test() -> None:
        client = AsyncGlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/",
            client_id="client-id",
            client_secret="client-secret",
        )
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

        async def fake_get_request(
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
            tickets = await client.search_ticket_records()

            assert [ticket.id for ticket in tickets] == ["1", "2", "3"]
            assert [request["start"] for request in requests] == [0, 2]
            assert all("limit" not in request for request in requests)
        finally:
            await client.close()

    asyncio.run(run_test())


def test_async_search_ticket_records_preserves_requested_unmodeled_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_test() -> None:
        client = AsyncGlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/",
            client_id="client-id",
            client_secret="client-secret",
        )

        async def fake_get_request(
            endpoint: str,
            params: dict[str, object] | None = None,
            skip_entity: bool = False,
        ) -> SearchResponse:
            assert endpoint == "Assistance/Ticket"
            assert skip_entity is False
            assert params is not None
            assert "resolution_date" in str(params.get("fields"))
            return SearchResponse(
                [
                    make_ticket_record(
                        id=1,
                        resolution_date="2026-01-15 11:45:00",
                        date_solve="2026-01-16 09:00:00",
                    )
                ],
                headers={"Content-Range": "0-0/1"},
            )

        monkeypatch.setattr(client, "_get_request", fake_get_request)
        try:
            tickets = await client.search_ticket_records(
                fields=("resolution_date", "date_solve"),
            )

            assert tickets[0].extra_payload == {
                "resolution_date": "2026-01-15 11:45:00",
                "date_solve": "2026-01-16 09:00:00",
            }
        finally:
            await client.close()

    asyncio.run(run_test())
