from __future__ import annotations

import asyncio

import pytest

from glpi_python_client import AsyncGlpiClient, GlpiFollowup, GlpiSolution
from glpi_python_client.testing.utils import FakeResponse


def _empty_response() -> FakeResponse:
    return FakeResponse(status_code=204, payload={}, text="", content=b"")


def test_async_update_followup_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_test() -> None:
        client = AsyncGlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/",
            client_id="client-id",
            client_secret="client-secret",
        )

        async def fake_update_request(
            endpoint: str,
            payload: dict[str, object] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            assert endpoint == "Assistance/Ticket/321/Timeline/Followup/654"
            assert skip_entity is False
            assert payload == {
                "content": "<p>Updated followup</p>",
                "is_private": False,
            }
            response = FakeResponse()
            response.status_code = 204
            response.text = ""
            response.content = b""
            return response

        monkeypatch.setattr(client, "_update_request", fake_update_request)
        try:
            await client.update_followup(
                "321",
                "654",
                GlpiFollowup(content="Updated followup"),
            )
        finally:
            await client.close()

    asyncio.run(run_test())


def test_async_create_solution_accepts_solution_id_response_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_test() -> None:
        client = AsyncGlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/",
            client_id="client-id",
            client_secret="client-secret",
        )

        async def fake_post_request(
            endpoint: str,
            payload: dict[str, object] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            assert endpoint == "Assistance/Ticket/321/Timeline/Solution"
            assert skip_entity is False
            assert payload == {"content": "<p>Resolved</p>"}
            return FakeResponse(payload={"solution_id": "987"})

        monkeypatch.setattr(client, "_post_request", fake_post_request)
        try:
            created = await client.create_solution(
                321,
                GlpiSolution(content="Resolved"),
            )

            assert created == "987"
        finally:
            await client.close()

    asyncio.run(run_test())


@pytest.mark.parametrize(
    ("method_name", "args", "expected_endpoint"),
    [
        ("delete_followup", (321, 654), "Assistance/Ticket/321/Timeline/Followup/654"),
        ("delete_solution", (321, 987), "Assistance/Ticket/321/Timeline/Solution/987"),
    ],
)
def test_async_delete_timeline_operations_return_none(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    args: tuple[object, ...],
    expected_endpoint: str,
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
            assert endpoint == expected_endpoint
            assert payload is None
            assert skip_entity is False
            return _empty_response()

        monkeypatch.setattr(client, "_delete_request", fake_delete_request)
        try:
            operation = getattr(client, method_name)
            await operation(*args)
        finally:
            await client.close()

    asyncio.run(run_test())
