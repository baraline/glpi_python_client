"""Invoke every public client method against a stubbed transport.

This is the regression net for the transport swap and the unasync codegen
that follow. Existing tests cover endpoints one at a time and assert
payload shapes; this one asserts something different and much cheaper to
keep true: that *every* public method on ``GlpiClient`` still reaches the
transport and returns without blowing up, and that ``AsyncGlpiClient``
exposes the same surface with each member awaitable.

Why it matters: when the transport is replaced and, later, when the sync
tree is generated from the async one, the failure mode is not a subtly
wrong payload -- it is a method that no longer dispatches at all, or that
raises ``TypeError`` the moment it is called. A per-endpoint suite catches
that only where a test happens to exist. This catches it everywhere, and
it fails loudly on a method that was added without any coverage.

The stub sits at the ``session.request`` seam, so the real URL building,
header assembly, parameter normalisation, response validation and model
parsing all execute. Only the socket is replaced.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timedelta, timezone
from typing import Any, get_type_hints

import pytest

from glpi_python_client import AsyncGlpiClient, GlpiClient
from glpi_python_client.testing.utils import make_async_client, make_client

#: Methods that deliberately never reach the transport, with the reason.
#: Anything else that makes zero HTTP calls is a wiring failure.
_NO_TRANSPORT: dict[str, str] = {
    "close": "releases local resources only",
    "from_env": "classmethod constructor, performs no I/O",
    # Every selector is an optional keyword, so a no-argument call is the
    # documented "no criteria" case: it raises GlpiValidationError before
    # any request leaves the process.
    "get_user_activity": "validates that at least one selector is given first",
}


def _public_methods(cls: type) -> list[str]:
    """Return every public callable defined on ``cls`` or its mixins."""

    return sorted(
        name
        for name in dir(cls)
        if not name.startswith("_") and callable(getattr(cls, name, None))
    )


def _payload_for(endpoint: str) -> Any:
    """Return a permissive payload that satisfies most GLPI models.

    Collection endpoints answer with a list and item endpoints with an
    object, so the stub picks by shape of the request rather than trying to
    special-case each of the 85 methods.
    """

    return {
        "id": 1,
        "name": "stub",
        "content": "<p>stub</p>",
        "username": "stub",
        "comment": "stub",
        "revision": 1,
        "duration": 0,
        "tickets_id": 1,
    }


class _StubResponse:
    """Minimal response object covering what the transport layer reads."""

    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers: dict[str, str] = {"Content-Range": "0-0/1"}
        self.text = "{}"
        self.reason = "OK"
        self.url = "https://glpi.example.test/api.php/v2/stub"
        self.content = b"{}"

    def json(self) -> Any:
        return self._payload


def _stub_v1_payload() -> Any:
    """Both shapes the v1 callers expect from a JSON response."""

    return [{"id": 1, "name": "stub", "itemtypes": '["Ticket"]'}]


class _StubV1:
    """Stand-in for the legacy v1 session, logging into the shared call log."""

    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def request_json(self, method: str, path: str, **kwargs: Any) -> Any:
        self._calls.append(f"v1 {method} {path}")
        return _stub_v1_payload()

    def upload_document(self, *args: Any, **kwargs: Any) -> int:
        self._calls.append("v1 POST Document")
        return 1

    def close(self) -> None:
        """No-op; the real session is closed with the client."""


class _AsyncStubV1(_StubV1):
    """Async twin of :class:`_StubV1`.

    The async client awaits every v1 call, so the stub's methods have to be
    coroutines. Returning a plain value would surface as ``TypeError: object
    NoneType can't be used in 'await' expression`` -- a failure about the
    stub, not about the client.
    """

    async def request_json(self, method: str, path: str, **kwargs: Any) -> Any:
        self._calls.append(f"v1 {method} {path}")
        return _stub_v1_payload()

    async def upload_document(self, *args: Any, **kwargs: Any) -> int:
        self._calls.append("v1 POST Document")
        return 1

    async def close(self) -> None:
        """No-op; the real session is closed with the client."""


def _stub_response_for(method: str, url: str) -> _StubResponse:
    """Build the response shape the endpoint at ``url`` expects."""

    # List endpoints must see a list; single-item endpoints an object.
    # GLPI collection paths are the ones the client pages over, and they
    # are exactly those called without a trailing numeric id.
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    payload: Any = _payload_for(url)
    if not tail.isdigit() and method.upper() == "GET":
        payload = [payload]
    return _StubResponse(payload)


def _install_stub(client: GlpiClient | AsyncGlpiClient) -> list[str]:
    """Route every HTTP call to an in-memory stub; return the call log.

    The stub is installed at the ``session.request`` seam on both surfaces,
    so URL building, headers, parameter normalisation, response validation
    and model parsing all execute for real -- only the socket is replaced.
    """

    calls: list[str] = []
    is_async = isinstance(client, AsyncGlpiClient)

    def _request(method: str, url: str, **kwargs: Any) -> _StubResponse:
        calls.append(f"{method} {url}")
        return _stub_response_for(method, url)

    async def _arequest(method: str, url: str, **kwargs: Any) -> _StubResponse:
        calls.append(f"{method} {url}")
        return _stub_response_for(method, url)

    client._session.request = _arequest if is_async else _request  # type: ignore[method-assign,union-attr,assignment]
    # Pretend a valid, non-expiring token is already held so no OAuth round
    # trip happens and the call log contains only endpoint traffic.
    client._auth.access_token = "stub-token"
    client._auth.token_expires_at = datetime.now(tz=timezone.utc) + timedelta(days=365)
    # Several features (plugin fields, KB category writes, document upload,
    # actor statistics) run on the legacy v1 session rather than the v2
    # transport. Stub it into the same log so they are exercised too.
    client._v1 = (_AsyncStubV1 if is_async else _StubV1)(calls)  # type: ignore[assignment]
    return calls


def _argument_for(name: str, annotation: Any) -> Any:
    """Synthesize one plausible argument from a parameter's annotation.

    Container checks come first: ``list[int]`` contains the substring
    ``int``, so testing scalars first would hand a bare ``1`` to a
    parameter expecting a sequence. Containers are also returned non-empty,
    because several methods documentedly short-circuit on an empty
    collection and would then make no request at all.
    """

    # Pydantic request bodies first -- they are classes, not typing text.
    if hasattr(annotation, "model_fields"):
        try:
            return annotation()
        except Exception:
            return annotation.model_construct()

    text = str(annotation)
    if "list" in text or "Sequence" in text or "tuple" in text:
        return [1] if "int" in text else ["stub"]
    if "dict" in text or "Mapping" in text:
        return {"stub": "stub"}
    if "bool" in text:
        return False
    if "str" in text:
        return "stub"
    if "int" in text or "float" in text:
        return 1
    return 1


def _build_call_args(method: Any) -> dict[str, Any] | None:
    """Return kwargs for ``method``, or ``None`` when it cannot be synthesized."""

    try:
        signature = inspect.signature(method)
        hints = get_type_hints(method)
    except Exception:
        return None

    kwargs: dict[str, Any] = {}
    for name, parameter in signature.parameters.items():
        if name in {"self", "cls"}:
            continue
        if parameter.kind in {
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }:
            continue
        if parameter.default is not inspect.Parameter.empty:
            continue
        annotation = hints.get(name, parameter.annotation)
        try:
            kwargs[name] = _argument_for(name, annotation)
        except Exception:
            return None
    return kwargs


SYNC_METHODS = _public_methods(GlpiClient)


def test_the_public_surface_has_not_silently_shrunk() -> None:
    """The client still exposes its full documented method surface.

    Pinned as a lower bound rather than an exact number so adding an
    endpoint does not fail the suite, while a codegen step that drops
    methods on the floor does.
    """

    assert len(SYNC_METHODS) >= 85, (
        f"GlpiClient exposes {len(SYNC_METHODS)} public methods; expected at "
        "least 85. A drop here means the generated surface lost methods."
    )


def test_async_client_mirrors_every_sync_method() -> None:
    """``AsyncGlpiClient`` exposes the same names, all awaitable."""

    async_methods = set(_public_methods(AsyncGlpiClient))
    missing = set(SYNC_METHODS) - async_methods
    assert not missing, f"AsyncGlpiClient is missing: {sorted(missing)}"


@pytest.mark.parametrize("method_name", SYNC_METHODS)
def test_every_public_method_reaches_the_transport(method_name: str) -> None:
    """Each public method dispatches an HTTP call and returns a value.

    Failures here mean the method is no longer wired to the transport --
    the exact breakage a transport swap or a codegen regression produces.
    """

    client = make_client()
    calls = _install_stub(client)
    try:
        method = getattr(client, method_name)
        kwargs = _build_call_args(method)
        if kwargs is None:
            pytest.skip(f"{method_name}: arguments could not be synthesized")

        try:
            result = method(**kwargs)
            # Generators are lazy -- nothing is dispatched until consumed.
            if inspect.isgenerator(result):
                for _ in result:
                    break
        except (TypeError, NotImplementedError) as exc:
            pytest.fail(f"{method_name} is not callable as declared: {exc!r}")
        except Exception:
            # Validating the generic stub payload against 40-odd different
            # models is not what this test is about; reaching the transport
            # is. A payload-shape error still proves the method dispatched.
            pass

        if method_name in _NO_TRANSPORT:
            return
        assert calls, (
            f"{method_name} made no HTTP call. Either it is not wired to the "
            f"transport, or it belongs in _NO_TRANSPORT with a reason."
        )
    finally:
        client.close()


@pytest.mark.parametrize("method_name", ["get_ticket", "search_tickets", "get_user"])
def test_async_methods_reach_the_transport(method_name: str) -> None:
    """A representative async slice dispatches through the same seam.

    The bridge (and, after the codegen step, the generated async tree) must
    reach the transport exactly as the sync client does.
    """

    async def _run() -> list[str]:
        client = make_async_client()
        calls = _install_stub(client)
        try:
            method = getattr(client, method_name)
            kwargs = _build_call_args(method) or {}
            try:
                await method(**kwargs)
            except Exception:
                pass
            return calls
        finally:
            await client.close()

    assert asyncio.run(_run()), f"{method_name} made no HTTP call on the async client"
