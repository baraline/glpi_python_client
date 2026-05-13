from __future__ import annotations

import asyncio

import pytest

from glpi_python_client import AsyncGlpiClient
from glpi_python_client.testing.utils import FakeResponse


def _empty_response() -> FakeResponse:
    return FakeResponse(status_code=204, payload={}, text="", content=b"")


def test_async_delete_document_returns_none(
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
            assert endpoint == "Management/Document/777"
            assert payload is None
            assert skip_entity is True
            return _empty_response()

        monkeypatch.setattr(client, "_delete_request", fake_delete_request)
        try:
            await client.delete_document(777)
        finally:
            await client.close()

    asyncio.run(run_test())
