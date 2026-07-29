"""In-memory client factory and transport stubs for this tree's unit tests.

One of a generated pair: the module is written once and
``unasync_build.py`` transforms it into its twin in the other tree.
``AsyncGlpiClient`` is already a substitution key, so each copy returns
the client of the tree it lands in while the factory stays spelled
``make_client`` on both sides -- call sites read identically wherever
they are. The same holds for the two recorder classes: each replaces a
client's four transport helpers with stubs that capture the call and hand
back a fixed response, so a mixin test can assert the endpoint, verb and
serialised body without any HTTP plumbing.

It lives beside the tree rather than in ``glpi_python_client.testing``
because that module is a published downstream helper whose factories must
keep their current names; this one has to change its return type when the
tree is transformed.
"""

from __future__ import annotations

from typing import Any

from glpi_python_client import AsyncGlpiClient
from glpi_python_client.testing.utils import DEFAULT_CLIENT_CONFIG, FakeResponse

__all__ = ["FailingTransportRecorder", "TransportRecorder", "make_client"]


def make_client(**overrides: object) -> AsyncGlpiClient:
    """Return a test client with no real HTTP plumbing.

    Any constructor keyword can be overridden while the rest of the shared
    base configuration is reused.
    """

    config = dict(DEFAULT_CLIENT_CONFIG)
    config.update(overrides)
    return AsyncGlpiClient(**config)  # type: ignore[arg-type]


class TransportRecorder:
    """Capture the four transport calls and answer with fixed responses.

    Installed over the client's request helpers so a mixin test can assert
    the endpoint, verb and serialised body without any HTTP plumbing.
    """

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

    def install(self, client: AsyncGlpiClient) -> None:
        """Replace the four transport helpers with capturing stubs."""

        async def _get(
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

        async def _post(
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

        async def _patch(
            endpoint: str, json_body: dict[str, Any] | None = None
        ) -> FakeResponse:
            self.calls.append(
                {"method": "PATCH", "endpoint": endpoint, "json": json_body}
            )
            return FakeResponse(status_code=self._patch_status, payload={})

        async def _delete(
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

        client._get_request = _get  # type: ignore[method-assign, assignment]
        client._post_request = _post  # type: ignore[method-assign, assignment]
        client._update_request = _patch  # type: ignore[method-assign, assignment]
        client._delete_request = _delete  # type: ignore[method-assign, assignment]


class FailingTransportRecorder(TransportRecorder):
    """Answer every verb with one fixed non-success status."""

    def __init__(self, status: int) -> None:
        super().__init__(
            get_status=status,
            get_payload={"err": "x"},
            post_status=status,
            patch_status=status,
            delete_status=status,
        )
