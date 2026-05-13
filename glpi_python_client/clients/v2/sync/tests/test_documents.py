from __future__ import annotations

from collections.abc import Callable

import pytest

from glpi_python_client import GlpiClient
from glpi_python_client.testing.utils import FakeResponse, SearchResponse


def _empty_response() -> FakeResponse:
    return FakeResponse(status_code=204, payload={}, text="", content=b"")


def test_get_document_records_can_skip_metadata_enrichment(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()
    metadata_calls: list[str] = []

    def fake_get_request(
        endpoint: str,
        params: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> SearchResponse:
        assert endpoint == "Assistance/Ticket/321/Timeline/Document"
        assert params is None
        assert skip_entity is False
        return SearchResponse([{"documents_id": 654, "name": "diagnostic.txt"}])

    def fake_get_document_record(document_id: str | int) -> None:
        metadata_calls.append(str(document_id))

    monkeypatch.setattr(client, "_get_request", fake_get_request)
    monkeypatch.setattr(client, "get_document_record", fake_get_document_record)
    try:
        documents = client.get_document_records(321, enrich_metadata=False)

        assert metadata_calls == []
        assert documents[0].document_id == "654"
        assert documents[0].filename == "diagnostic.txt"
    finally:
        client.close()


def test_get_document_records_logs_metadata_enrichment_failures(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = client_factory()

    def fake_get_request(
        endpoint: str,
        params: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> SearchResponse:
        assert endpoint == "Assistance/Ticket/321/Timeline/Document"
        assert params is None
        assert skip_entity is False
        return SearchResponse([{"documents_id": 654, "name": "diagnostic.txt"}])

    def fake_get_document_record(document_id: str | int) -> None:
        raise ValueError(f"document {document_id} unavailable")

    monkeypatch.setattr(client, "_get_request", fake_get_request)
    monkeypatch.setattr(client, "get_document_record", fake_get_document_record)
    caplog.set_level("WARNING", logger="glpi_python_client.clients.v2.sync")
    try:
        documents = client.get_document_records(321)

        assert documents[0].document_id == "654"
        assert "Skipping GLPI document 654 metadata lookup" in caplog.text
    finally:
        client.close()


def test_delete_document_returns_none(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()

    def fake_delete_request(
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
        client.delete_document(777)
    finally:
        client.close()
