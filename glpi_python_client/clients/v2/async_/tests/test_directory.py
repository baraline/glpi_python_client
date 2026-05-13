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
