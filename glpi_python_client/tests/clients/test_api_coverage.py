"""Coverage-focused tests for every public ``GlpiClient`` API mixin method.

The tests reuse the recorder pattern from :mod:`test_smoke` to assert
endpoint URLs, HTTP verbs and serialised request bodies for the search,
get, update and delete operations that the existing smoke tests do not
already cover.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import (
    GlpiClient,
    GlpiValidationError,
    PatchDocument,
    PatchLocation,
    PostDocument,
)
from glpi_python_client.testing.utils import FakeResponse, make_client


class _Recorder:
    """Async transport recorder that drives FakeResponse responses."""

    def __init__(
        self,
        *,
        get_payload: Any = None,
        get_status: int = 200,
        get_content: bytes | None = None,
        post_payload: Any = None,
        post_status: int = 201,
        patch_status: int = 204,
        delete_status: int = 204,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._get_payload = get_payload if get_payload is not None else []
        self._get_status = get_status
        self._get_content = get_content
        self._post_payload = post_payload if post_payload is not None else {"id": 999}
        self._post_status = post_status
        self._patch_status = patch_status
        self._delete_status = delete_status

    def install(self, client: GlpiClient) -> None:
        """Replace the four transport helpers with capturing stubs."""

        def _get(
            endpoint: str,
            params: dict[str, Any] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            self.calls.append(
                {
                    "method": "GET",
                    "endpoint": endpoint,
                    "params": params,
                    "skip_entity": skip_entity,
                }
            )
            return FakeResponse(
                status_code=self._get_status,
                payload=self._get_payload,
                content=self._get_content,
            )

        def _post(
            endpoint: str,
            json_body: dict[str, Any] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            self.calls.append(
                {
                    "method": "POST",
                    "endpoint": endpoint,
                    "json": json_body,
                    "skip_entity": skip_entity,
                }
            )
            return FakeResponse(
                status_code=self._post_status, payload=self._post_payload
            )

        def _patch(
            endpoint: str, json_body: dict[str, Any] | None = None
        ) -> FakeResponse:
            self.calls.append(
                {"method": "PATCH", "endpoint": endpoint, "json": json_body}
            )
            return FakeResponse(status_code=self._patch_status, payload={})

        def _delete(
            endpoint: str,
            json_body: dict[str, Any] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            self.calls.append(
                {
                    "method": "DELETE",
                    "endpoint": endpoint,
                    "json": json_body,
                    "skip_entity": skip_entity,
                }
            )
            return FakeResponse(status_code=self._delete_status, payload={})

        client._get_request = _get  # type: ignore[method-assign]
        client._post_request = _post  # type: ignore[method-assign]
        client._update_request = _patch  # type: ignore[method-assign]
        client._delete_request = _delete  # type: ignore[method-assign]


@pytest.fixture
def client() -> GlpiClient:
    """Return one in-memory client without any real HTTP plumbing."""

    return make_client()


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------


def test_search_locations_passes_filter(client: GlpiClient) -> None:
    """``search_locations`` forwards the RSQL filter through ``filter``."""

    rec = _Recorder(get_payload=[{"id": 1, "name": "Paris"}])
    rec.install(client)
    locations = client.search_locations("name==Paris")
    assert locations[0].id == 1
    assert rec.calls[0]["endpoint"] == "Dropdowns/Location"
    assert rec.calls[0]["params"]["filter"] == "name==Paris"


def test_get_location_endpoint(client: GlpiClient) -> None:
    """``get_location`` hits the per-id endpoint."""

    rec = _Recorder(get_payload={"id": 9, "name": "Paris"})
    rec.install(client)
    loc = client.get_location(9)
    assert loc.id == 9
    assert rec.calls[0]["endpoint"] == "Dropdowns/Location/9"


def test_update_location(client: GlpiClient) -> None:
    """``update_location`` patches the per-id endpoint."""

    rec = _Recorder()
    rec.install(client)
    client.update_location(9, PatchLocation(name="Paris HQ"))
    assert rec.calls[0]["endpoint"] == "Dropdowns/Location/9"


def test_delete_location_with_force(client: GlpiClient) -> None:
    """``delete_location(force=True)`` ships the force flag in the body."""

    rec = _Recorder()
    rec.install(client)
    client.delete_location(9, force=True)
    call = rec.calls[0]
    assert call["method"] == "DELETE"
    assert call["endpoint"] == "Dropdowns/Location/9"
    assert call["json"] == {"force": True}


# ---------------------------------------------------------------------------
# Documents (management)
# ---------------------------------------------------------------------------


def test_search_documents_filter_and_pagination(client: GlpiClient) -> None:
    """``search_documents`` forwards the filter, limit, start, and skip_entity."""

    rec = _Recorder(get_payload=[{"id": 1, "name": "doc"}])
    rec.install(client)
    docs = client.search_documents("name==*manual*", limit=10, start=20)
    assert len(docs) == 1
    call = rec.calls[0]
    assert call["endpoint"] == "Management/Document"
    assert call["skip_entity"] is True
    assert call["params"]["limit"] == 10
    assert call["params"]["start"] == 20
    assert call["params"]["filter"] == "name==*manual*"


def test_get_document_endpoint(client: GlpiClient) -> None:
    """``get_document`` hits the per-id endpoint."""

    rec = _Recorder(get_payload={"id": 3, "name": "doc"})
    rec.install(client)
    document = client.get_document(3)
    assert document.id == 3
    assert rec.calls[0]["endpoint"] == "Management/Document/3"


def test_create_document_returns_id(client: GlpiClient) -> None:
    """``create_document`` returns the new id and skips entity."""

    rec = _Recorder(post_payload={"id": 77})
    rec.install(client)
    document_id = client.create_document(PostDocument(name="manual"))
    assert document_id == 77
    assert rec.calls[0]["endpoint"] == "Management/Document"
    assert rec.calls[0]["skip_entity"] is True


def test_update_document_patches_endpoint(client: GlpiClient) -> None:
    """``update_document`` issues PATCH on the per-id endpoint."""

    rec = _Recorder()
    rec.install(client)
    client.update_document(3, PatchDocument(name="x"))
    assert rec.calls[0]["endpoint"] == "Management/Document/3"


def test_delete_document_with_force(client: GlpiClient) -> None:
    """``delete_document(force=True)`` adds the body and skips entity."""

    rec = _Recorder()
    rec.install(client)
    client.delete_document(3, force=True)
    call = rec.calls[0]
    assert call["endpoint"] == "Management/Document/3"
    assert call["json"] == {"force": True}
    assert call["skip_entity"] is True


def test_download_document_returns_bytes(client: GlpiClient) -> None:
    """``download_document_content`` returns the response bytes."""

    rec = _Recorder(
        get_status=200, get_payload={"ignored": True}, get_content=b"\x00ZZ"
    )
    rec.install(client)
    content = client.download_document_content(3)
    assert content == b"\x00ZZ"
    assert rec.calls[0]["endpoint"] == "Management/Document/3/Download"


def test_download_document_raises_on_failure(client: GlpiClient) -> None:
    """A non-200 download status raises ``ValueError``."""

    rec = _Recorder(get_status=404, get_payload={"err": "missing"})
    rec.install(client)
    with pytest.raises(ValueError):
        client.download_document_content(3)


def test_upload_document_requires_filename(client: GlpiClient) -> None:
    """``upload_document`` rejects an empty filename before any HTTP call.

    ``GlpiValidationError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working.
    """

    with pytest.raises(GlpiValidationError, match="filename") as excinfo:
        client.upload_document(filename="", content=b"x")
    assert isinstance(excinfo.value, ValueError)


def test_upload_document_dispatches_to_v1(client: GlpiClient) -> None:
    """``upload_document`` forwards arguments to the configured v1 session."""

    captured: dict[str, Any] = {}

    class _FakeV1:
        def upload_document(
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

    client._v1 = _FakeV1()  # type: ignore[assignment]
    result = client.upload_document(
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


# ---------------------------------------------------------------------------
# Generic error handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_location(1),
        lambda c: c.get_document(1),
    ],
)
def test_get_helpers_raise_on_failure_status(
    client: GlpiClient, call: Callable[[GlpiClient], Any]
) -> None:
    """Every read helper raises ``ValueError`` on a non-success status."""

    rec = _Recorder(get_status=404, get_payload={"err": "missing"})
    rec.install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.update_location(1, PatchLocation(name="x")),
        lambda c: c.update_document(1, PatchDocument(name="x")),
    ],
)
def test_update_helpers_raise_on_failure_status(
    client: GlpiClient, call: Callable[[GlpiClient], Any]
) -> None:
    """Every update helper raises ``ValueError`` on a non-success status."""

    rec = _Recorder(patch_status=500)
    rec.install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.delete_location(1, force=True),
        lambda c: c.delete_document(1, force=True),
    ],
)
def test_delete_helpers_raise_on_failure_status(
    client: GlpiClient, call: Callable[[GlpiClient], Any]
) -> None:
    """Every delete helper raises ``ValueError`` on a non-success status."""

    rec = _Recorder(delete_status=500)
    rec.install(client)
    with pytest.raises(ValueError):
        call(client)
