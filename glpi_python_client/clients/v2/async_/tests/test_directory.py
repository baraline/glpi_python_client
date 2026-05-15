from __future__ import annotations

import asyncio

import pytest

from glpi_python_client import AsyncGlpiClient
from glpi_python_client.testing.utils import SearchResponse


def test_async_search_locations_escapes_query_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_test() -> None:
        client = AsyncGlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/",
            client_id="client-id",
            client_secret="client-secret",
        )
        observed_params: dict[str, object] | None = None

        async def fake_get_request(
            endpoint: str,
            params: dict[str, object] | None = None,
            skip_entity: bool = False,
        ) -> SearchResponse:
            nonlocal observed_params
            assert endpoint == "Dropdowns/Location"
            assert skip_entity is False
            observed_params = params
            return SearchResponse([])

        monkeypatch.setattr(client, "_get_request", fake_get_request)
        try:
            await client.search_locations('Paris "HQ" *East\\West')

            assert observed_params == {
                "filter": 'name=like="*Paris \\"HQ\\" \\*East\\\\West*"'
            }
        finally:
            await client.close()

    asyncio.run(run_test())


def test_async_search_entities_returns_typed_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_test() -> None:
        client = AsyncGlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/",
            client_id="client-id",
            client_secret="client-secret",
        )
        observed_requests: list[tuple[str, dict[str, object] | None, bool]] = []

        async def fake_get_request(
            endpoint: str,
            params: dict[str, object] | None = None,
            skip_entity: bool = False,
        ) -> SearchResponse:
            observed_requests.append((endpoint, params, skip_entity))
            assert endpoint == "Administration/Entity"
            assert params == {
                "start": 5,
                "limit": 10,
                "filter": "name=like=*novahe*",
            }
            assert skip_entity is True
            return SearchResponse(
                [
                    {
                        "id": 42,
                        "name": "Novahe",
                        "completename": "Root > Novahe",
                    }
                ]
            )

        monkeypatch.setattr(client, "_get_request", fake_get_request)
        try:
            entities = await client.search_entities(
                rsql_filter="name=like=*novahe*",
                limit=10,
                start=5,
            )

            assert len(observed_requests) == 1
            assert entities[0].entity_id == "42"
            assert entities[0].complete_name == "Root > Novahe"
        finally:
            await client.close()

    asyncio.run(run_test())
