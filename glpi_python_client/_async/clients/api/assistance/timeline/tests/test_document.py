"""Unit tests for the ``Assistance/Ticket/Timeline/Document`` endpoint mixin.

The tests cover listing, fetching, linking, updating, and unlinking ticket
timeline documents, using the shared transport recorders to stub the four
transport helpers without any HTTP plumbing.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta, timezone
from typing import Any

import pytest

from glpi_python_client import (
    GetDocumentItem,
    GlpiStatusError,
    GlpiValidationError,
    PatchTimelineDocument,
    PostTimelineDocument,
)
from glpi_python_client._async._testing import (
    FailingTransportRecorder,
    TransportRecorder,
)


async def test_list_get_update_unlink_timeline_documents(client: Any) -> None:
    """All four timeline document helpers target the document endpoint."""

    rec = TransportRecorder(
        get_payload=[
            {"type": "Document_Item", "item": {"id": 1, "filename": "report.txt"}},
        ]
    )
    rec.install(client)
    items = await client.list_ticket_timeline_documents(7)
    assert items[0].id == 1
    assert rec.calls[0]["endpoint"] == "Assistance/Ticket/7/Timeline/Document"

    rec._get_payload = {"id": 1, "filename": "report.txt"}  # type: ignore[attr-defined]
    doc = await client.get_ticket_timeline_document(7, 1)
    assert doc.id == 1

    await client.update_ticket_timeline_document(7, 1, PatchTimelineDocument())
    await client.unlink_ticket_timeline_document(7, 1, force=True)

    methods = [c["method"] for c in rec.calls]
    assert methods == ["GET", "GET", "PATCH", "DELETE"]


async def test_link_ticket_timeline_document_targets_document_endpoint(
    client: Any,
) -> None:
    """``link_ticket_timeline_document`` targets the document timeline endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    await client.link_ticket_timeline_document(10, PostTimelineDocument())
    call = rec.calls[0]
    assert call["endpoint"] == "Assistance/Ticket/10/Timeline/Document"
    assert call["json"] == {}


# ---------------------------------------------------------------------------
# Generic error handling (this mixin's share of the shared failure suites)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_ticket_timeline_document(1, 2),
        lambda c: c.list_ticket_timeline_documents(1),
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
        lambda c: c.update_ticket_timeline_document(1, 2, PatchTimelineDocument()),
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
        lambda c: c.unlink_ticket_timeline_document(1, 2, force=True),
    ],
)
async def test_delete_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every delete helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        await call(client)


class _FakeV1:
    """Stand-in for the v1 session that records ``request_json`` calls."""

    def __init__(self, response: object, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, object] | None = None,
        failure_message: str | None = None,
    ) -> object:
        self.calls.append({"method": method, "path": path, "params": params})
        if self.error is not None:
            raise self.error
        return self.response

    async def close(self) -> None:
        """No-op; the real session is closed with the client."""


def _link_row(row_id: int = 1, documents_id: int = 11) -> dict[str, Any]:
    return {
        "id": row_id,
        "documents_id": documents_id,
        "items_id": 7,
        "itemtype": "ITILFollowup",
        "entities_id": 0,
        "is_recursive": 0,
        "date": "2026-01-02 03:04:05",
        "timeline_position": -1,
    }


async def test_list_item_documents_reads_the_followup_route(client: Any) -> None:
    """The call is a v1 GET on the item's Document_Item sub-route."""

    fake = _FakeV1([_link_row()])
    client._v1 = fake
    rows = await client.list_item_documents("ITILFollowup", 7)
    assert len(fake.calls) == 1
    assert fake.calls[0]["method"] == "GET"
    assert fake.calls[0]["path"] == "ITILFollowup/7/Document_Item"
    assert fake.calls[0]["params"] == {"range": "0-999"}
    assert isinstance(rows[0], GetDocumentItem)
    assert rows[0].documents_id == 11
    assert rows[0].itemtype == "ITILFollowup"
    assert rows[0].items_id == 7


async def test_list_item_documents_localises_dates(client: Any) -> None:
    """Naive link dates gain the client's server timezone."""

    zone = timezone(timedelta(hours=2))
    client.server_timezone = zone
    client._v1 = _FakeV1([_link_row()])
    rows = await client.list_item_documents("ITILFollowup", 7)
    assert rows[0].date is not None
    assert rows[0].date.utcoffset() == timedelta(hours=2)


async def test_list_item_documents_uses_the_given_itemtype(client: Any) -> None:
    """A task call puts its own itemtype and id in the path."""

    fake = _FakeV1([])
    client._v1 = fake
    await client.list_item_documents("TicketTask", 42)
    assert fake.calls[0]["path"] == "TicketTask/42/Document_Item"


async def test_list_item_documents_empty_answers(client: Any) -> None:
    """An empty list and the empty-body ``{}`` both give no rows."""

    client._v1 = _FakeV1([])
    assert await client.list_item_documents("ITILFollowup", 7) == []
    client._v1 = _FakeV1({})
    assert await client.list_item_documents("ITILFollowup", 7) == []


@pytest.mark.parametrize("answer", [{"a": 1}, "text", None])
async def test_list_item_documents_rejects_other_payloads(
    client: Any, answer: object
) -> None:
    """Anything but a list or ``{}`` raises instead of reading as empty."""

    client._v1 = _FakeV1(answer)
    with pytest.raises(GlpiValidationError):
        await client.list_item_documents("ITILFollowup", 7)


async def test_list_item_documents_needs_a_v1_session(client: Any) -> None:
    """Without a v1 session the call raises ``RuntimeError``."""

    assert client._v1 is None
    with pytest.raises(RuntimeError, match="v1 session"):
        await client.list_item_documents("ITILFollowup", 7)


@pytest.mark.parametrize(
    ("itemtype", "items_id"),
    [
        ("ITIL/Followup", 7),
        ("ITIL Followup", 7),
        ("..", 7),
        ("", 7),
        ("1Followup", 7),
        ("ITILFollowup", 0),
        ("ITILFollowup", -3),
    ],
)
async def test_list_item_documents_validates_before_any_call(
    client: Any, itemtype: str, items_id: int
) -> None:
    """A bad itemtype or id raises before the session is touched."""

    fake = _FakeV1([])
    client._v1 = fake
    with pytest.raises(GlpiValidationError):
        await client.list_item_documents(itemtype, items_id)
    assert fake.calls == []


async def test_list_item_documents_propagates_status_errors(client: Any) -> None:
    """A 4xx raised by the session reaches the caller."""

    client._v1 = _FakeV1(
        [],
        error=GlpiStatusError("denied", status_code=403, url="https://glpi.example/x"),
    )
    with pytest.raises(GlpiStatusError):
        await client.list_item_documents("ITILFollowup", 7)


async def test_list_item_documents_returns_999_rows_whole(client: Any) -> None:
    """One row under the page size is a complete answer."""

    client._v1 = _FakeV1([_link_row(i, i) for i in range(1, 1000)])
    rows = await client.list_item_documents("ITILFollowup", 7)
    assert len(rows) == 999


async def test_list_item_documents_refuses_a_full_page(client: Any) -> None:
    """A full page may be truncated, so it raises and returns no partial list."""

    client._v1 = _FakeV1([_link_row(i, i) for i in range(1, 1001)])
    with pytest.raises(GlpiValidationError):
        await client.list_item_documents("ITILFollowup", 7)
