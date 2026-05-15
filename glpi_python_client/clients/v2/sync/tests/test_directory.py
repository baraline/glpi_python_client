from __future__ import annotations

from collections.abc import Callable

import pytest

from glpi_python_client import GlpiClient
from glpi_python_client.testing.utils import SearchResponse


def test_search_locations_escapes_query_text(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()
    observed_params: dict[str, object] | None = None

    def fake_get_request(
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
        client.search_locations('Paris "HQ" *East\\West')

        assert observed_params == {
            "filter": 'name=like="*Paris \\"HQ\\" \\*East\\\\West*"'
        }
    finally:
        client.close()


def test_search_locations_returns_empty_for_blank_query(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()

    def fake_get_request(
        endpoint: str,
        params: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> SearchResponse:
        raise AssertionError("blank location search should not call GLPI")

    monkeypatch.setattr(client, "_get_request", fake_get_request)
    try:
        assert client.search_locations("  ") == []
    finally:
        client.close()


def test_search_entities_returns_typed_records(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()
    observed_requests: list[tuple[str, dict[str, object] | None, bool]] = []

    def fake_get_request(
        endpoint: str,
        params: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> SearchResponse:
        observed_requests.append((endpoint, params, skip_entity))
        assert endpoint == "Administration/Entity"
        assert params == {
            "start": 10,
            "limit": 25,
            "filter": "name=like=*novahe*",
        }
        assert skip_entity is True
        return SearchResponse(
            [
                {
                    "id": 42,
                    "name": "Novahe",
                    "complete_name": "Root > Novahe",
                    "comment": "Customer entity",
                }
            ]
        )

    monkeypatch.setattr(client, "_get_request", fake_get_request)
    try:
        entities = client.search_entities(
            rsql_filter="name=like=*novahe*",
            limit=25,
            start=10,
        )

        assert len(observed_requests) == 1
        assert entities[0].entity_id == "42"
        assert entities[0].complete_name == "Root > Novahe"
    finally:
        client.close()
