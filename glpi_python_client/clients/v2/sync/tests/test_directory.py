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
