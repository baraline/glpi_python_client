"""Unit tests for the ``Management/Document`` endpoint mixin.

The tests cover search, fetch, create, update, delete, download, and
upload for GLPI documents, using the shared transport recorders to stub
the four transport helpers without any HTTP plumbing. The upload tests
additionally stub the legacy v1 session used for binary uploads.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import GlpiValidationError, PatchDocument, PostDocument
from glpi_python_client._async._testing import (
    FailingTransportRecorder,
    TransportRecorder,
)

# ---------------------------------------------------------------------------
# Documents (management)
# ---------------------------------------------------------------------------


async def test_search_documents_filter_and_pagination(client: Any) -> None:
    """``search_documents`` forwards the filter, limit, start, and skip_entity."""

    rec = TransportRecorder(get_payload=[{"id": 1, "name": "doc"}])
    rec.install(client)
    docs = await client.search_documents("name==*manual*", limit=10, start=20)
    assert len(docs) == 1
    call = rec.calls[0]
    assert call["endpoint"] == "Management/Document"
    assert call["skip_entity"] is True
    assert call["params"]["limit"] == 10
    assert call["params"]["start"] == 20
    assert call["params"]["filter"] == "name==*manual*"


async def test_get_document_endpoint(client: Any) -> None:
    """``get_document`` hits the per-id endpoint."""

    rec = TransportRecorder(get_payload={"id": 3, "name": "doc"})
    rec.install(client)
    document = await client.get_document(3)
    assert document.id == 3
    assert rec.calls[0]["endpoint"] == "Management/Document/3"


async def test_create_document_returns_id(client: Any) -> None:
    """``create_document`` returns the new id and skips entity."""

    rec = TransportRecorder(post_payload={"id": 77})
    rec.install(client)
    document_id = await client.create_document(PostDocument(name="manual"))
    assert document_id == 77
    assert rec.calls[0]["endpoint"] == "Management/Document"
    assert rec.calls[0]["skip_entity"] is True


async def test_update_document_patches_endpoint(client: Any) -> None:
    """``update_document`` issues PATCH on the per-id endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    await client.update_document(3, PatchDocument(name="x"))
    assert rec.calls[0]["endpoint"] == "Management/Document/3"


async def test_delete_document_with_force(client: Any) -> None:
    """``delete_document(force=True)`` adds the body and skips entity."""

    rec = TransportRecorder()
    rec.install(client)
    await client.delete_document(3, force=True)
    call = rec.calls[0]
    assert call["endpoint"] == "Management/Document/3"
    assert call["json"] == {"force": True}
    assert call["skip_entity"] is True


async def test_download_document_returns_bytes(client: Any) -> None:
    """``download_document_content`` returns the response bytes."""

    rec = TransportRecorder(
        get_status=200, get_payload={"ignored": True}, get_content=b"\x00ZZ"
    )
    rec.install(client)
    content = await client.download_document_content(3)
    assert content == b"\x00ZZ"
    assert rec.calls[0]["endpoint"] == "Management/Document/3/Download"


async def test_download_document_raises_on_failure(client: Any) -> None:
    """A non-200 download status raises ``ValueError``."""

    rec = TransportRecorder(get_status=404, get_payload={"err": "missing"})
    rec.install(client)
    with pytest.raises(ValueError):
        await client.download_document_content(3)


async def test_upload_document_requires_filename(client: Any) -> None:
    """``upload_document`` rejects an empty filename before any HTTP call.

    ``GlpiValidationError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working.
    """

    with pytest.raises(GlpiValidationError, match="filename") as excinfo:
        await client.upload_document(filename="", content=b"x")
    assert isinstance(excinfo.value, ValueError)


async def test_upload_document_dispatches_to_v1(client: Any) -> None:
    """``upload_document`` forwards arguments to the configured v1 session."""

    captured: dict[str, Any] = {}

    class _FakeV1:
        """Stand-in for the legacy v1 session used by document upload."""

        async def upload_document(
            self,
            filename: str,
            content: bytes,
            mime_type: str,
            *,
            document_name: str | None,
            ticket_id: int | None,
            entity_id: int | None,
        ) -> dict[str, object]:
            captured.update(
                {
                    "filename": filename,
                    "content": content,
                    "mime_type": mime_type,
                    "document_name": document_name,
                    "ticket_id": ticket_id,
                    "entity_id": entity_id,
                }
            )
            return {"id": 1}

        async def close(self) -> None:
            """No-op; the real session is closed with the client."""

    client._v1 = _FakeV1()  # type: ignore[assignment]
    result = await client.upload_document(
        filename="a.txt",
        content=b"abc",
        mime_type="text/plain",
        document_name="DocA",
        ticket_id=5,
        entity_id=2,
    )

    assert result == {"id": 1}
    assert captured["filename"] == "a.txt"
    assert captured["ticket_id"] == 5
    assert captured["entity_id"] == 2


async def test_upload_document_without_v1_raises(client: Any) -> None:
    """``upload_document`` requires a v1 session to be configured."""

    with pytest.raises(RuntimeError):
        await client.upload_document(
            filename="a.bin",
            content=b"x",
        )


# ---------------------------------------------------------------------------
# Generic error handling (this mixin's share of the shared failure suites)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_document(1),
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
        lambda c: c.update_document(1, PatchDocument(name="x")),
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
        lambda c: c.delete_document(1, force=True),
    ],
)
async def test_delete_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every delete helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        await call(client)


async def test_iter_search_documents_yields_every_page(client: Any) -> None:
    """The generator advances ``start`` until a short page ends the walk."""

    from glpi_python_client.models.api_schema.management import GetDocument

    pages = [[GetDocument(id=i) for i in range(3)], [GetDocument(id=99)]]
    starts: list[int] = []

    async def fake_search(
        rsql_filter: str = "", *, limit: int = 50, start: int = 0
    ) -> list[GetDocument]:
        starts.append(start)
        index = start // limit
        return pages[index] if index < len(pages) else []

    client.search_documents = fake_search  # type: ignore[method-assign]

    batches = [
        batch async for batch in client.iter_search_documents("name==x", batch_size=3)
    ]

    assert starts == [0, 3]
    assert [len(b) for b in batches] == [3, 1]


async def test_iter_search_documents_stops_on_a_single_short_page(client: Any) -> None:
    """One short page is the last page; no second request is made."""

    from glpi_python_client.models.api_schema.management import GetDocument

    starts: list[int] = []

    async def fake_search(
        rsql_filter: str = "", *, limit: int = 50, start: int = 0
    ) -> list[GetDocument]:
        starts.append(start)
        return [GetDocument(id=1)]

    client.search_documents = fake_search  # type: ignore[method-assign]

    batches = [batch async for batch in client.iter_search_documents(batch_size=50)]

    assert starts == [0]
    assert len(batches) == 1


async def test_iter_search_documents_yields_nothing_when_empty(client: Any) -> None:
    """An empty first page yields no batch at all rather than one empty list."""

    from glpi_python_client.models.api_schema.management import GetDocument

    async def fake_search(
        rsql_filter: str = "", *, limit: int = 50, start: int = 0
    ) -> list[GetDocument]:
        return []

    client.search_documents = fake_search  # type: ignore[method-assign]

    assert [batch async for batch in client.iter_search_documents()] == []
