"""Unit tests for the published :mod:`glpi_python_client.testing` helpers.

These are the only part of ``testing/`` that downstream suites import, and
the library's own tests reach for the per-tree ``_testing`` twins instead --
so nothing else here exercises them. Before this module, ``SearchResponse``,
``TicketResponse`` and the ``client_factory`` fixture shipped with no test
at all: their lines sat behind a coverage ``omit`` that matched the whole
``testing/`` package rather than just its suites.
"""

from __future__ import annotations

from collections.abc import Callable

from glpi_python_client import GlpiClient
from glpi_python_client.testing import (
    DEFAULT_CLIENT_CONFIG,
    FakeResponse,
    SearchResponse,
    TicketResponse,
    TokenResponse,
)


def test_search_response_carries_a_list_payload_and_defaults_to_200() -> None:
    """``SearchResponse`` wraps a record list without restating the status."""

    records = [{"id": 1}, {"id": 2}]
    response = SearchResponse(records)

    assert response.status_code == 200
    assert response.json() == records
    assert response.headers == {}


def test_search_response_forwards_status_and_headers() -> None:
    """The overrides reach the ``FakeResponse`` base unchanged."""

    response = SearchResponse(
        [{"id": 1}],
        status_code=206,
        headers={"Content-Range": "0-0/1"},
    )

    assert response.status_code == 206
    assert response.headers == {"Content-Range": "0-0/1"}


def test_ticket_response_carries_one_record_and_defaults_to_200() -> None:
    """``TicketResponse`` wraps a single mapping, not a list."""

    ticket = {"id": 7, "name": "printer jam"}
    response = TicketResponse(ticket)

    assert response.status_code == 200
    assert response.json() == ticket


def test_ticket_response_forwards_status() -> None:
    """A non-default status reaches the base class."""

    assert TicketResponse({"id": 7}, status_code=201).status_code == 201


def test_the_fake_responses_are_all_fake_response_subclasses() -> None:
    """Downstream code may type against the base; the subclasses honour it."""

    assert issubclass(SearchResponse, FakeResponse)
    assert issubclass(TicketResponse, FakeResponse)
    assert issubclass(TokenResponse, FakeResponse)


def test_client_factory_fixture_builds_a_usable_client(
    client_factory: Callable[..., GlpiClient],
) -> None:
    """The published pytest fixture yields a working client factory.

    ``conftest.py`` registers ``glpi_python_client.testing.fixtures`` as a
    plugin, but no other test in this repository requests the fixture, so
    this is the only thing proving the published entry point resolves and
    returns something usable.
    """

    client = client_factory()
    try:
        assert isinstance(client, GlpiClient)
        assert client.glpi_api_url == "https://glpi.example.test/api.php"
    finally:
        client.close()


def test_client_factory_fixture_accepts_overrides(
    client_factory: Callable[..., GlpiClient],
) -> None:
    """Overrides replace one default without restating the others."""

    client = client_factory(glpi_api_url="https://other.example.test/api.php/")
    try:
        assert client.glpi_api_url == "https://other.example.test/api.php"
        # Untouched defaults still come from the shared configuration.
        assert client._auth._client_id == DEFAULT_CLIENT_CONFIG["client_id"]
    finally:
        client.close()
