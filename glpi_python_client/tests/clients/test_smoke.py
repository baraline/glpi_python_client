"""Smoke tests covering the asynchronous API mixin call paths.

The tests stub the asynchronous transport helpers on a real
:class:`GlpiClient` instance to exercise the per-endpoint mixins without
performing any network call. They focus on the interaction between mixins
and the transport layer and ensure the contract-aligned models are
serialised into the expected request bodies.
"""

from __future__ import annotations

from typing import Any

import pytest

from glpi_python_client import (
    GlpiClient,
    PostLocation,
    PostUser,
)
from glpi_python_client.testing.utils import FakeResponse, make_client


class _Recorder:
    """Lightweight async stub recording transport calls for assertions."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def install(self, client: GlpiClient) -> None:
        """Replace the transport methods on ``client`` with recording stubs."""

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
            return FakeResponse(status_code=200, payload=self._next_get_payload())

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
            return FakeResponse(status_code=201, payload={"id": 999})

        def _patch(
            endpoint: str, json_body: dict[str, Any] | None = None
        ) -> FakeResponse:
            self.calls.append(
                {"method": "PATCH", "endpoint": endpoint, "json": json_body}
            )
            return FakeResponse(status_code=204, payload={})

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
            return FakeResponse(status_code=204, payload={})

        client._get_request = _get  # type: ignore[method-assign]
        client._post_request = _post  # type: ignore[method-assign]
        client._update_request = _patch  # type: ignore[method-assign]
        client._delete_request = _delete  # type: ignore[method-assign]

    def _next_get_payload(self) -> object:
        """Return a simple representative GET payload for list endpoints."""

        return [{"id": 1, "name": "demo"}]


@pytest.fixture
def client() -> GlpiClient:
    """Return one in-memory test client without any real HTTP plumbing."""

    return make_client()


@pytest.fixture
def recorder(client: GlpiClient) -> _Recorder:
    """Return one transport recorder already wired onto ``client``."""

    rec = _Recorder()
    rec.install(client)
    return rec


def test_create_user_serialises_post_body(
    client: GlpiClient, recorder: _Recorder
) -> None:
    """``create_user`` serialises the ``PostUser`` model into the POST body."""

    user_id = client.create_user(PostUser(username="alice"))
    assert user_id == 999
    assert recorder.calls == [
        {
            "method": "POST",
            "endpoint": "Administration/User",
            "json": {"username": "alice"},
            "skip_entity": False,
        }
    ]


def test_create_entity_skips_entity_header(
    client: GlpiClient, recorder: _Recorder
) -> None:
    """Entity create requests bypass the GLPI-Entity header."""

    from glpi_python_client import PostEntity

    client.create_entity(PostEntity(name="root"))
    call = recorder.calls[0]
    assert call["endpoint"] == "Administration/Entity"
    assert call["skip_entity"] is True


def test_delete_user_supports_force_flag(
    client: GlpiClient, recorder: _Recorder
) -> None:
    """``delete_user`` forwards the ``force`` flag inside the JSON body."""

    client.delete_user(5, force=True)
    call = recorder.calls[0]
    assert call["method"] == "DELETE"
    assert call["endpoint"] == "Administration/User/5"
    assert call["json"] == {"force": True}


def test_create_location_targets_dropdown_endpoint(
    client: GlpiClient, recorder: _Recorder
) -> None:
    """``create_location`` posts to the dropdown endpoint."""

    client.create_location(PostLocation(name="Paris"))
    call = recorder.calls[0]
    assert call["endpoint"] == "Dropdowns/Location"


def test_upload_document_without_v1_raises(client: GlpiClient) -> None:
    """``upload_document`` requires a v1 session to be configured."""

    with pytest.raises(RuntimeError):
        client.upload_document(
            filename="a.bin",
            content=b"x",
        )
