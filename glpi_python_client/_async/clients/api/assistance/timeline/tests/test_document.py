"""Unit tests for the ``Assistance/Ticket/Timeline/Document`` endpoint mixin.

The tests cover listing, fetching, linking, updating, and unlinking ticket
timeline documents, using the shared transport recorders to stub the four
transport helpers without any HTTP plumbing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import PatchTimelineDocument, PostTimelineDocument
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
