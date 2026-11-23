"""Unit tests for the pending-reason client mixin."""

from __future__ import annotations

from typing import Any

import pytest

from glpi_python_client import GlpiProtocolError, PendingReason, PendingReasonItem
from glpi_python_client._async._testing import TransportRecorder


class _FakeV1:
    """Stand-in for the v1 session that replays queued ``request_json`` answers."""

    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, object] | None = None,
        json_body: dict[str, object] | None = None,
        success_statuses: tuple[int, ...] = (200, 201, 204, 206),
        failure_message: str | None = None,
    ) -> object:
        self.calls.append({"method": method, "path": path, "json_body": json_body})
        if not self.responses:
            raise AssertionError(f"Unexpected v1 call: {method} {path}")
        return self.responses.pop(0)

    async def close(self) -> None:
        """No-op; the real session is closed with the client."""


_ITEM = {
    "id": 5,
    "itemtype": "Ticket",
    "items_id": 42,
    "pendingreasons_id": 3,
    "followup_frequency": 3600,
    "followups_before_resolution": 2,
    "bump_count": 0,
    "last_bump_date": None,
    "previous_status": 2,
}


async def test_list_pending_reasons_reads_the_v2_catalogue(client: Any) -> None:
    """The catalogue is a paged v2 read of ``Assistance/PendingReason``."""

    rec = TransportRecorder(
        get_payload=[
            {
                "id": 3,
                "name": "Waiting for the requester",
                "is_default": True,
                "followup_frequency": 86400,
                "followups_before_resolution": 3,
                "entity": {"id": 0, "name": "Root"},
            }
        ]
    )
    rec.install(client)
    reasons = await client.list_pending_reasons("name==x", limit=10, start=5)
    assert isinstance(reasons[0], PendingReason)
    assert reasons[0].followup_frequency == 86400
    call = rec.calls[0]
    assert call["endpoint"] == "Assistance/PendingReason"
    assert call["params"] == {"limit": 10, "start": 5, "filter": "name==x"}


async def test_iter_pending_reasons_stops_on_a_short_page(client: Any) -> None:
    """The iterator yields a page shorter than ``batch_size`` and stops."""

    rec = TransportRecorder(get_payload=[{"id": 1}])
    rec.install(client)
    pages = [page async for page in client.iter_pending_reasons(batch_size=2)]
    assert [[r.id for r in page] for page in pages] == [[1]]
    assert rec.calls[0]["params"] == {"limit": 2, "start": 0}


async def test_get_ticket_pending_reason_present(client: Any) -> None:
    """A ticket's item is read with v1 ``GET Ticket/{id}/PendingReason_Item``."""

    fake = _FakeV1([[_ITEM]])
    client._v1 = fake  # type: ignore[assignment]
    item = await client.get_ticket_pending_reason(42)
    assert isinstance(item, PendingReasonItem)
    assert item.pendingreasons_id == 3
    assert item.previous_status == 2
    assert fake.calls == [
        {"method": "GET", "path": "Ticket/42/PendingReason_Item", "json_body": None}
    ]


async def test_get_ticket_pending_reason_absent(client: Any) -> None:
    """An empty list means the ticket has no item."""

    client._v1 = _FakeV1([[]])  # type: ignore[assignment]
    assert await client.get_ticket_pending_reason(42) is None


async def test_set_ticket_pending_reason_posts_when_no_item(client: Any) -> None:
    """With no item the reason is created with POST and never PUT."""

    fake = _FakeV1([[], {"id": 5, "message": ""}, [_ITEM]])
    client._v1 = fake  # type: ignore[assignment]
    item = await client.set_ticket_pending_reason(
        42, 3, followup_frequency=3600, followups_before_resolution=2
    )
    assert item.id == 5
    assert [c["method"] for c in fake.calls] == ["GET", "POST", "GET"]
    assert fake.calls[1]["path"] == "PendingReason_Item"
    assert fake.calls[1]["json_body"] == {
        "input": {
            "itemtype": "Ticket",
            "items_id": 42,
            "pendingreasons_id": 3,
            "followup_frequency": 3600,
            "followups_before_resolution": 2,
        }
    }


async def test_set_ticket_pending_reason_defaults_send_zero(client: Any) -> None:
    """The frequencies default to 0 and are always sent."""

    fake = _FakeV1([[], {"id": 5}, [_ITEM]])
    client._v1 = fake  # type: ignore[assignment]
    await client.set_ticket_pending_reason(42, 3)
    body = fake.calls[1]["json_body"]
    assert body["input"]["followup_frequency"] == 0
    assert body["input"]["followups_before_resolution"] == 0


async def test_set_ticket_pending_reason_puts_when_item_exists(client: Any) -> None:
    """With an item the reason is changed with PUT and never POST."""

    fake = _FakeV1([[_ITEM], [{"5": True, "message": ""}], [_ITEM]])
    client._v1 = fake  # type: ignore[assignment]
    item = await client.set_ticket_pending_reason(42, 4, followup_frequency=60)
    assert item.id == 5
    assert [c["method"] for c in fake.calls] == ["GET", "PUT", "GET"]
    assert fake.calls[1]["path"] == "PendingReason_Item/5"
    assert fake.calls[1]["json_body"] == {
        "input": {
            "id": 5,
            "pendingreasons_id": 4,
            "followup_frequency": 60,
            "followups_before_resolution": 0,
        }
    }


async def test_set_ticket_pending_reason_rejects_unreadable_result(
    client: Any,
) -> None:
    """A write that leaves no readable item raises a protocol error."""

    client._v1 = _FakeV1([[], {"id": 5}, []])  # type: ignore[assignment]
    with pytest.raises(GlpiProtocolError):
        await client.set_ticket_pending_reason(42, 3)


async def test_clear_ticket_pending_reason_deletes_the_item(client: Any) -> None:
    """Clearing deletes the ticket's item and reports it."""

    fake = _FakeV1([[_ITEM], [{"5": True, "message": ""}]])
    client._v1 = fake  # type: ignore[assignment]
    assert await client.clear_ticket_pending_reason(42) is True
    assert [c["method"] for c in fake.calls] == ["GET", "DELETE"]
    assert fake.calls[1]["path"] == "PendingReason_Item/5"


async def test_clear_ticket_pending_reason_without_item_sends_no_delete(
    client: Any,
) -> None:
    """With no item the answer is False and nothing is deleted."""

    fake = _FakeV1([[]])
    client._v1 = fake  # type: ignore[assignment]
    assert await client.clear_ticket_pending_reason(42) is False
    assert [c["method"] for c in fake.calls] == ["GET"]


async def test_ticket_methods_need_the_v1_session(client: Any) -> None:
    """The three ticket methods raise the missing-v1-session error."""

    assert client._v1 is None
    with pytest.raises(RuntimeError, match="v1 session"):
        await client.get_ticket_pending_reason(42)
    with pytest.raises(RuntimeError, match="v1 session"):
        await client.set_ticket_pending_reason(42, 3)
    with pytest.raises(RuntimeError, match="v1 session"):
        await client.clear_ticket_pending_reason(42)
