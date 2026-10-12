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
    FollowupDocuments,
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


class _RoutedV1:
    """V1 stand-in that answers per path and records every path asked."""

    def __init__(self, routes: dict[str, object]) -> None:
        self.routes = routes
        self.paths: list[str] = []

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, object] | None = None,
        failure_message: str | None = None,
    ) -> object:
        self.paths.append(path)
        answer = self.routes[path]
        if isinstance(answer, Exception):
            raise answer
        return answer

    async def close(self) -> None:
        """No-op; the real session is closed with the client."""


def _followup(followup_id: int | None, is_private: bool | None) -> dict[str, Any]:
    row: dict[str, Any] = {"content": "text"}
    if followup_id is not None:
        row["id"] = followup_id
    if is_private is not None:
        row["is_private"] = is_private
    return row


def _followup_link(
    followup_id: int, documents_id: int, **overrides: Any
) -> dict[str, Any]:
    row = _link_row(row_id=documents_id + 100, documents_id=documents_id)
    row["items_id"] = followup_id
    row.update(overrides)
    return row


def _install_followups(client: Any, followups: list[dict[str, Any]]) -> None:
    TransportRecorder(get_payload=followups).install(client)


async def test_followup_documents_lists_public_followups_in_id_order(
    client: Any,
) -> None:
    """Public followups come back by ascending id, links attached, empties kept."""

    _install_followups(client, [_followup(12, False), _followup(11, False)])
    fake = _RoutedV1(
        {
            "ITILFollowup/11/Document_Item": [
                _followup_link(11, 21),
                _followup_link(11, 22),
            ],
            "ITILFollowup/12/Document_Item": [],
        }
    )
    client._v1 = fake
    entries = await client.list_ticket_followup_documents(7)
    assert all(isinstance(entry, FollowupDocuments) for entry in entries)
    assert [entry.followup.id for entry in entries] == [11, 12]
    assert [d.documents_id for d in entries[0].documents] == [21, 22]
    assert entries[1].documents == []
    assert sorted(fake.paths) == [
        "ITILFollowup/11/Document_Item",
        "ITILFollowup/12/Document_Item",
    ]


async def test_followup_documents_skips_private_and_flagless_by_default(
    client: Any,
) -> None:
    """Private and flag-less followups are absent and never queried."""

    _install_followups(
        client, [_followup(11, False), _followup(12, True), _followup(13, None)]
    )
    fake = _RoutedV1({"ITILFollowup/11/Document_Item": [_followup_link(11, 21)]})
    client._v1 = fake
    entries = await client.list_ticket_followup_documents(7)
    assert [entry.followup.id for entry in entries] == [11]
    assert fake.paths == ["ITILFollowup/11/Document_Item"]


async def test_followup_documents_include_private_keeps_every_followup(
    client: Any,
) -> None:
    """With ``include_private`` every followup is listed, flags intact."""

    _install_followups(
        client, [_followup(13, None), _followup(11, False), _followup(12, True)]
    )
    client._v1 = _RoutedV1(
        {
            "ITILFollowup/11/Document_Item": [_followup_link(11, 21)],
            "ITILFollowup/12/Document_Item": [_followup_link(12, 22)],
            "ITILFollowup/13/Document_Item": [],
        }
    )
    entries = await client.list_ticket_followup_documents(7, include_private=True)
    assert [entry.followup.id for entry in entries] == [11, 12, 13]
    assert [entry.followup.is_private for entry in entries] == [False, True, None]
    assert [len(entry.documents) for entry in entries] == [1, 1, 0]


async def test_followup_documents_drops_foreign_link_rows(client: Any) -> None:
    """A row naming another followup or another itemtype is dropped."""

    _install_followups(client, [_followup(11, False)])
    client._v1 = _RoutedV1(
        {
            "ITILFollowup/11/Document_Item": [
                _followup_link(11, 21),
                _followup_link(12, 22),
                _followup_link(11, 23, itemtype="Ticket"),
                _followup_link(11, 24, items_id=None),
            ]
        }
    )
    entries = await client.list_ticket_followup_documents(7)
    assert [d.documents_id for d in entries[0].documents] == [21]


async def test_followup_documents_propagates_a_failed_read(client: Any) -> None:
    """One failing followup read fails the call, with no partial list."""

    _install_followups(client, [_followup(11, False), _followup(12, False)])
    client._v1 = _RoutedV1(
        {
            "ITILFollowup/11/Document_Item": [_followup_link(11, 21)],
            "ITILFollowup/12/Document_Item": GlpiValidationError("boom"),
        }
    )
    with pytest.raises(GlpiValidationError, match="boom"):
        await client.list_ticket_followup_documents(7)


async def test_followup_documents_rejects_a_followup_without_an_id(
    client: Any,
) -> None:
    """A followup that cannot be queried raises rather than being skipped."""

    _install_followups(client, [_followup(11, False), _followup(None, False)])
    fake = _RoutedV1({"ITILFollowup/11/Document_Item": []})
    client._v1 = fake
    with pytest.raises(GlpiValidationError):
        await client.list_ticket_followup_documents(7)


async def test_followup_documents_without_a_v1_session_raises(client: Any) -> None:
    """The v1 session is required even when no followup exists."""

    _install_followups(client, [])
    with pytest.raises(RuntimeError):
        await client.list_ticket_followup_documents(7)


async def test_followup_documents_no_followups_gives_empty_list(client: Any) -> None:
    """A ticket without followups gives an empty list."""

    _install_followups(client, [])
    client._v1 = _RoutedV1({})
    assert await client.list_ticket_followup_documents(7) == []
