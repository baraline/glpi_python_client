"""Unit tests for the ``Assistance/Ticket`` endpoint mixin.

The tests cover search, fetch, create, update, delete, and page-by-page
iteration for GLPI tickets, using the shared transport recorders to stub
the four transport helpers without any HTTP plumbing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import PatchTicket, PostTicket
from glpi_python_client._async._testing import (
    FailingTransportRecorder,
    TransportRecorder,
)

# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------


async def test_search_tickets_forwards_sort_and_fields(client: Any) -> None:
    """Sort and field selection both flow into the GET query parameters."""

    rec = TransportRecorder(get_payload=[{"id": 1, "name": "n", "content": "c"}])
    rec.install(client)
    tickets = await client.search_tickets(
        "status==1", limit=5, start=10, sort="date_mod desc", fields=("id", "name")
    )

    assert len(tickets) == 1
    assert rec.calls[0]["params"]["filter"] == "status==1"
    assert rec.calls[0]["params"]["limit"] == 5
    assert rec.calls[0]["params"]["start"] == 10
    assert rec.calls[0]["params"]["sort"] == "date_mod desc"
    assert rec.calls[0]["params"]["fields"] == "id,name"


async def test_search_tickets_uses_filter_query_param(client: Any) -> None:
    """``search_tickets`` forwards the RSQL filter via the ``filter`` parameter."""

    rec = TransportRecorder(get_payload=[{"id": 1, "name": "demo"}])
    rec.install(client)
    tickets = await client.search_tickets(rsql_filter="status==1", limit=20)
    assert len(tickets) == 1
    assert rec.calls[0]["method"] == "GET"
    assert rec.calls[0]["endpoint"] == "Assistance/Ticket"
    assert rec.calls[0]["params"]["filter"] == "status==1"
    assert rec.calls[0]["params"]["limit"] == 20


async def test_get_ticket_returns_validated_model(client: Any) -> None:
    """Single ticket responses are validated through ``GetTicket``."""

    rec = TransportRecorder(
        get_payload={"id": 7, "name": "demo", "content": "<p>c</p>"}
    )
    rec.install(client)
    ticket = await client.get_ticket(7)
    assert ticket.id == 7
    assert rec.calls[0]["endpoint"] == "Assistance/Ticket/7"


async def test_create_ticket_serialises_enums(client: Any) -> None:
    """``create_ticket`` serialises enum values as their numeric form."""

    rec = TransportRecorder()
    rec.install(client)
    await client.create_ticket(PostTicket(name="t", content="<p>c</p>"))
    call = rec.calls[0]
    assert call["endpoint"] == "Assistance/Ticket"
    assert call["json"]["name"] == "t"


async def test_update_ticket_sends_patch(client: Any) -> None:
    """Update sends a PATCH with the partial body."""

    rec = TransportRecorder()
    rec.install(client)
    await client.update_ticket(7, PatchTicket(content="<p>x</p>"))
    call = rec.calls[0]
    assert call["method"] == "PATCH"
    assert call["endpoint"] == "Assistance/Ticket/7"
    assert call["json"] == {"content": "<p>x</p>"}


async def test_delete_ticket_omits_body_without_force(client: Any) -> None:
    """``delete_ticket(force=None)`` omits the JSON body."""

    rec = TransportRecorder()
    rec.install(client)
    await client.delete_ticket(7)
    call = rec.calls[0]
    assert call["method"] == "DELETE"
    assert call["endpoint"] == "Assistance/Ticket/7"
    assert call["json"] is None


# ---------------------------------------------------------------------------
# Generic error handling (this mixin's share of the shared failure suites)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_ticket(1),
    ],
)
async def test_get_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every read helper raises on a non-success status."""

    FailingTransportRecorder(404).install(client)
    with pytest.raises(ValueError):
        await call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.update_ticket(1, PatchTicket(content="<p>x</p>")),
    ],
)
async def test_update_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every update helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        await call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.delete_ticket(1, force=True),
    ],
)
async def test_delete_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every delete helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        await call(client)


# ---------------------------------------------------------------------------
# iter_search_tickets
# ---------------------------------------------------------------------------


async def test_iter_search_tickets_single_page(client: Any) -> None:
    """A response shorter than batch_size yields one batch then stops."""

    pages: list[list[Any]] = [[{"id": 1, "name": "t1", "content": "c"}]]
    call_count = 0

    async def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
        fields: tuple[str, ...] = (),
    ) -> list[Any]:
        nonlocal call_count
        call_count += 1
        return pages[0]

    client.search_tickets = fake_search  # type: ignore[method-assign]
    batches = [b async for b in client.iter_search_tickets("status==1", batch_size=50)]
    assert call_count == 1
    assert len(batches) == 1
    assert len(batches[0]) == 1


async def test_iter_search_tickets_multi_page_stops_on_short_batch(
    client: Any,
) -> None:
    """Iteration stops after the first batch shorter than batch_size."""

    ticket_a = {"id": 1, "name": "a", "content": "c"}
    ticket_b = {"id": 2, "name": "b", "content": "c"}
    ticket_c = {"id": 3, "name": "c", "content": "c"}
    responses = [
        [ticket_a, ticket_b],  # full page → continue
        [ticket_c],  # short page → last
    ]
    call_count = 0

    async def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
        fields: tuple[str, ...] = (),
    ) -> list[Any]:
        nonlocal call_count
        result = responses[min(call_count, len(responses) - 1)]
        call_count += 1
        return result

    client.search_tickets = fake_search  # type: ignore[method-assign]
    batches = [batch async for batch in client.iter_search_tickets("", batch_size=2)]
    assert call_count == 2
    assert len(batches) == 2
    assert len(batches[0]) == 2
    assert len(batches[1]) == 1


async def test_iter_search_tickets_forwards_pagination_and_query_options(
    client: Any,
) -> None:
    """Each page advances ``start`` and repeats the caller's query options.

    The sibling tests above count pages and stub the search away, so they
    pass whatever the generator sends. This one records every call: it is
    the only thing pinning the offset arithmetic and the per-page
    forwarding of ``filter``, ``sort`` and ``fields``.
    """

    ticket = {"id": 1, "name": "a", "content": "c"}
    responses = [[ticket, ticket], [ticket, ticket], [ticket]]
    calls: list[dict[str, Any]] = []

    async def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
        fields: tuple[str, ...] = (),
    ) -> list[Any]:
        calls.append(
            {
                "rsql_filter": rsql_filter,
                "limit": limit,
                "start": start,
                "sort": sort,
                "fields": fields,
            }
        )
        return responses[len(calls) - 1]

    client.search_tickets = fake_search  # type: ignore[method-assign]
    batches = [
        batch
        async for batch in client.iter_search_tickets(
            "status==1", batch_size=2, sort="id:desc", fields=("id", "name")
        )
    ]

    assert len(batches) == 3
    # One full page per step. A generator that failed to advance the offset
    # would re-request page zero forever against a real server.
    assert [call["start"] for call in calls] == [0, 2, 4]
    assert [call["limit"] for call in calls] == [2, 2, 2]
    # Every page repeats the caller's options. Forwarding them only on the
    # first request would silently change the sort order and widen the
    # field set from page two onwards.
    assert all(call["rsql_filter"] == "status==1" for call in calls)
    assert all(call["sort"] == "id:desc" for call in calls)
    assert all(call["fields"] == ("id", "name") for call in calls)
