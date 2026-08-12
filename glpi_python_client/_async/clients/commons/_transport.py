"""GLPI v2 transport mixin.

The transport mixin owns token handling, header construction, retries, and
HTTP request dispatch so the per-endpoint mixins under
:mod:`glpi_python_client._async.clients.api` can stay focused on resource-specific
behaviour.

Concurrency model
-----------------
Access to the auth token manager is serialised with the lock from
:mod:`glpi_python_client._async._concurrency`. That module is one of only
two maintained separately for each surface, because the correct primitive
genuinely differs: an :class:`asyncio.Lock` for concurrent tasks on one
event loop, a :class:`threading.Lock` for a client shared across threads.
Neither substitutes for the other -- see that module for what breaks in
each direction.

The lock is held only for the short critical section that refreshes the
token. HTTP calls run outside it, so concurrent callers proceed in
parallel while sharing one access token. The underlying HTTP client is
safe for that concurrent use; it is built once at construction and never
mutated afterwards.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING, Any, TypeVar

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from glpi_python_client._async._concurrency import Lock
from glpi_python_client._async.clients.commons._http import (
    build_request_headers,
    build_request_url,
    ensure_response_status,
    finalize_request_response,
    list_payload_items,
    request_params,
    require_access_token,
    require_response_int,
    transport_error_from,
    unwrap_timeline_items,
)
from glpi_python_client._async.clients.commons._payloads import (
    model_from_payload,
    model_to_payload,
)
from glpi_python_client._errors import GlpiServerError, GlpiTransportError
from glpi_python_client.models._base import GlpiModel

if TYPE_CHECKING:
    from glpi_python_client._async.auth._v1_session import GLPIV1Session
    from glpi_python_client._async.auth.auth import GLPITokenManager

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=GlpiModel)

#: Shared retry policy for every v2 transport verb.
#:
#: Declared once rather than repeated on each of the four verb helpers, and
#: expressed entirely in library-owned exception types. Both parts are
#: deliberate. A predicate that names the HTTP library's own exception base
#: stops matching the moment the transport is swapped — the exception trees of
#: the different libraries are completely disjoint — and retries then vanish
#: with no error, no warning and a green test suite. Naming
#: :class:`~glpi_python_client.GlpiTransportError`, which
#: :func:`~glpi_python_client._async.clients.commons._http.transport_error_from`
#: guarantees every network fault is translated into, makes that failure
#: impossible to reintroduce.
_RETRY_ON_NETWORK_ERRORS = retry(
    retry=retry_if_exception_type((GlpiTransportError, GlpiServerError)),
    stop=stop_after_attempt(3),
    wait=wait_fixed(3),
    reraise=True,
)


class TransportMixin:
    """GLPI API transport helpers shared by the API mixins.

    The class declares the runtime attributes the concrete client owns and
    exposes the blocking ``_get_request``, ``_post_request``,
    ``_update_request`` and ``_delete_request`` helpers used by every
    per-endpoint mixin.

    Thread safety
    -------------
    Token acquisition and refresh are serialised by ``_auth_lock``, the
    ``Lock`` from :mod:`glpi_python_client._async._concurrency`, so
    concurrent callers never race while updating shared authentication
    state. That module is hand-written on both surfaces because the
    right primitive differs in kind between them. HTTP dispatch runs
    outside the lock and relies on the underlying httpx client being
    safe to use from concurrent callers.
    """

    _auth: GLPITokenManager
    _auth_lock: Lock
    _closed: bool = False
    _session: httpx.AsyncClient
    _v1: GLPIV1Session | None
    entity_recursive: bool
    glpi_api_url: str
    glpi_entity: int | None
    glpi_profile: int | None
    language: str

    def _ensure_open(self) -> None:
        """Raise when the client has already been closed.

        All transport helpers call this guard before touching the shared
        HTTP session so closed clients fail fast and predictably.
        """

        if self._closed:
            raise RuntimeError("GLPI client is closed")

    def _require_v1_session(self, feature: str) -> GLPIV1Session:
        """Return the configured v1 session or raise ``RuntimeError``.

        Parameters
        ----------
        feature : str
            Short label of the caller (for example ``"document upload"``
            or ``"Fields plugin helpers"``) embedded in the error message
            so users learn which client option to set.

        Returns
        -------
        GLPIV1Session
            The legacy v1 session bundled with the client.

        Raises
        ------
        RuntimeError
            When the client was built without ``v1_base_url`` and
            ``v1_user_token``.
        """

        if self._v1 is None:
            raise RuntimeError(
                f"GLPI {feature} require the legacy v1 session to be configured "
                "(set v1_base_url and v1_user_token)."
            )
        return self._v1

    async def _ensure_token(self) -> None:
        """Ensure that a valid GLPI access token is available.

        Token refresh is serialised by ``_auth_lock`` so concurrent
        callers from any thread never race while updating shared
        authentication state.
        """

        self._ensure_open()
        async with self._auth_lock:
            await self._auth.ensure_token()

    async def _send_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Dispatch one blocking HTTP call.

        The helper exists as an indirection seam so tests can stub HTTP
        dispatch without monkey-patching the session attribute directly.

        Dispatch goes through ``session.request(method, url, ...)`` rather
        than looking up a per-verb attribute, keeping the verb a value
        instead of an attribute name.

        Transport-level failures are translated into
        :class:`~glpi_python_client.GlpiTransportError` (or
        :class:`~glpi_python_client.GlpiTimeoutError`) here, at the single
        point where the HTTP library is actually called, so no third-party
        exception escapes into the caller's ``except`` clauses.

        Raises
        ------
        GlpiTransportError
            When the request never produced a response.
        """

        try:
            return await self._session.request(method.upper(), url, **kwargs)
        except httpx.HTTPError as exc:
            raise transport_error_from(exc, method=method, url=url) from exc

    async def _stream_request(
        self,
        endpoint: str,
        *,
        chunk_size: int,
        skip_entity: bool = False,
        failure_message: str,
    ) -> AsyncIterator[bytes]:
        """Stream one authenticated GLPI ``GET`` body in chunks.

        The non-streaming helpers materialise the whole body before the
        caller sees any of it, which is fine for JSON and wrong for a
        document that may be hundreds of megabytes.

        Two details differ from the buffered path and both are load-bearing.
        The status has to be checked *inside* the context manager, and the
        body read first: the error helpers format the response text, and
        reading text off an unread stream raises rather than reporting the
        status. And no retry decorator belongs here -- tenacity does not
        wrap an async generator, so a decorator would silently degrade to
        the sync path instead of failing loudly.

        Raises
        ------
        GlpiStatusError
            When the response status is not 200.
        GlpiTransportError
            When the request never produced a response.
        """

        await self._ensure_token()
        access_token = require_access_token(self._auth.access_token)
        url = build_request_url(self.glpi_api_url, endpoint)
        headers = build_request_headers(
            access_token=access_token,
            language=self.language,
            glpi_entity=self.glpi_entity,
            glpi_profile=self.glpi_profile,
            entity_recursive=self.entity_recursive,
            include_content_type=False,
            skip_entity=skip_entity,
        )

        try:
            async with self._session.stream(
                "GET", url, headers=headers, timeout=30
            ) as response:
                if response.status_code != 200:
                    await response.aread()
                    ensure_response_status(
                        response,
                        success_statuses=(200,),
                        failure_message=failure_message,
                    )
                async for chunk in response.aiter_bytes(chunk_size):
                    yield chunk
        except httpx.HTTPError as exc:
            raise transport_error_from(exc, method="get", url=url) from exc

    async def _execute_request(
        self,
        *,
        method: str,
        endpoint: str,
        success_statuses: tuple[int, ...],
        params: dict[str, object] | None = None,
        json_body: dict[str, object] | None = None,
        skip_entity: bool = False,
        include_content_type: bool = False,
    ) -> httpx.Response:
        """Execute one authenticated GLPI request.

        The helper normalises the endpoint URL, headers, timeout, and
        payload placement before dispatching the blocking HTTP call. It
        guarantees a fresh access token before the request leaves the
        process.
        """

        await self._ensure_token()
        access_token = require_access_token(self._auth.access_token)
        url = build_request_url(self.glpi_api_url, endpoint)

        request_kwargs: dict[str, object] = {
            "headers": build_request_headers(
                access_token=access_token,
                language=self.language,
                glpi_entity=self.glpi_entity,
                glpi_profile=self.glpi_profile,
                entity_recursive=self.entity_recursive,
                include_content_type=include_content_type,
                skip_entity=skip_entity,
            ),
            "timeout": 30,
        }
        if method == "get":
            request_kwargs["params"] = request_params(params)
        else:
            request_kwargs["json"] = json_body

        response = await self._send_request(method, url, **request_kwargs)
        return finalize_request_response(
            response,
            method=method,
            url=url,
            success_statuses=success_statuses,
            logger=logger,
        )

    @_RETRY_ON_NETWORK_ERRORS
    async def _get_request(
        self,
        endpoint: str,
        params: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> httpx.Response:
        """Execute one authenticated GLPI ``GET`` request.

        Network errors (:class:`~glpi_python_client.GlpiTransportError`) and 5xx
        responses (:class:`~glpi_python_client.GlpiServerError`) are
        retried up to 3 times, with ``reraise=True`` so the real error
        propagates once retries are exhausted; 4xx responses are
        returned as-is without a retry.
        """

        return await self._execute_request(
            method="get",
            endpoint=endpoint,
            success_statuses=(200, 206),
            params=params,
            skip_entity=skip_entity,
        )

    @_RETRY_ON_NETWORK_ERRORS
    async def _post_request(
        self,
        endpoint: str,
        json_body: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> httpx.Response:
        """Execute one authenticated GLPI ``POST`` request.

        JSON request bodies automatically include the content-type header
        needed by the GLPI API.
        """

        return await self._execute_request(
            method="post",
            endpoint=endpoint,
            success_statuses=(200, 201),
            json_body=json_body,
            skip_entity=skip_entity,
            include_content_type=True,
        )

    @_RETRY_ON_NETWORK_ERRORS
    async def _update_request(
        self,
        endpoint: str,
        json_body: dict[str, object] | None = None,
    ) -> httpx.Response:
        """Execute one authenticated GLPI ``PATCH`` request.

        The helper uses the same authenticated execution path as the
        other HTTP verbs while targeting the success codes expected from
        update calls.
        """

        return await self._execute_request(
            method="patch",
            endpoint=endpoint,
            success_statuses=(200, 204),
            json_body=json_body,
            include_content_type=True,
        )

    @_RETRY_ON_NETWORK_ERRORS
    async def _delete_request(
        self,
        endpoint: str,
        json_body: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> httpx.Response:
        """Execute one authenticated GLPI ``DELETE`` request.

        Some delete endpoints accept a JSON body, so the content-type
        header is enabled automatically when a body is supplied.
        """

        return await self._execute_request(
            method="delete",
            endpoint=endpoint,
            success_statuses=(200, 204),
            json_body=json_body,
            skip_entity=skip_entity,
            include_content_type=json_body is not None,
        )

    async def _resource_list(
        self,
        endpoint: str,
        model: type[ModelT],
        *,
        params: dict[str, object] | None = None,
        skip_entity: bool = False,
        failure_message: str | None = None,
        success_statuses: tuple[int, ...] = (200, 206),
        unwrap_envelope: bool = False,
    ) -> list[ModelT]:
        """Run a GLPI list/search request and validate every returned record.

        Parameters
        ----------
        endpoint : str
            Resource path forwarded to the transport ``GET`` helper.
        model : type[ModelT]
            Pydantic class used to validate each item from the response.
        params : dict[str, object] | None, optional
            Query parameters forwarded to the underlying ``GET`` request.
        skip_entity : bool, optional
            When ``True`` the ``GLPI-Entity`` header is omitted.
        failure_message : str | None, optional
            Message embedded in the raised ``GlpiStatusError``. ``None``
            derives one from the endpoint; the status is checked either
            way.
        success_statuses : tuple[int, ...], optional
            HTTP status codes considered successful when
            ``failure_message`` is set.
        unwrap_envelope : bool, optional
            When ``True`` the GLPI timeline ``{"type", "item"}`` envelope
            is unwrapped before validation.

        Returns
        -------
        list[ModelT]
            Validated records returned by the GLPI server.
        """

        response = await self._get_request(
            endpoint, params=params, skip_entity=skip_entity
        )
        # The status is checked on every list call, search included. It used
        # not to be, and a refused search then came back as ``[]``: a 403 was
        # indistinguishable from a filter that matched nothing. It composed
        # badly with the batch iterators, which stop on a page shorter than
        # ``batch_size`` -- so a 403 on page one ended the walk having
        # yielded nothing and the caller saw a successful empty result. An
        # empty list now means the server said the result set is empty.
        ensure_response_status(
            response,
            success_statuses=success_statuses,
            failure_message=failure_message or f"Failed to list {endpoint}",
        )
        payload = response.json()
        items = (
            unwrap_timeline_items(payload)
            if unwrap_envelope
            else list_payload_items(payload)
        )
        return [model_from_payload(model, item) for item in items]

    async def _resource_get(
        self,
        endpoint: str,
        model: type[ModelT],
        *,
        failure_message: str,
        skip_entity: bool = False,
    ) -> ModelT:
        """Fetch one record and validate it against ``model``.

        Parameters
        ----------
        endpoint : str
            Resource path forwarded to the transport ``GET`` helper.
        model : type[ModelT]
            Pydantic class used to validate the response payload.
        failure_message : str
            Message embedded in the ``GlpiStatusError`` raised on a
            non-success HTTP status.
        skip_entity : bool, optional
            When ``True`` the ``GLPI-Entity`` header is omitted.

        Returns
        -------
        ModelT
            Validated record returned by the GLPI server.
        """

        response = await self._get_request(endpoint, skip_entity=skip_entity)
        ensure_response_status(
            response,
            success_statuses=(200, 206),
            failure_message=failure_message,
        )
        return model_from_payload(model, response.json())

    async def _resource_create(
        self,
        endpoint: str,
        body_model: GlpiModel,
        *,
        failure_message: str,
        missing_message: str,
        log_message_factory: Callable[[int], str],
        id_keys: tuple[str, ...] = ("id",),
        skip_entity: bool = False,
    ) -> int:
        """Create one record and return the identifier assigned by GLPI.

        Parameters
        ----------
        endpoint : str
            Resource path forwarded to the transport ``POST`` helper.
        body_model : GlpiModel
            Pydantic body serialised through :func:`model_to_payload`.
        failure_message : str
            Message embedded in the ``GlpiStatusError`` raised on a
            non-success HTTP status.
        missing_message : str
            Message embedded in the ``GlpiProtocolError`` raised when the
            response payload does not contain any of the expected
            identifier keys.
        log_message_factory : Callable[[int], str]
            Callable invoked with the new identifier to build the
            ``logger.info`` payload, allowing call sites to embed the
            parent context (for example a ticket id).
        id_keys : tuple[str, ...], optional
            Candidate keys probed in the response when looking up the
            identifier of the newly created record.
        skip_entity : bool, optional
            When ``True`` the ``GLPI-Entity`` header is omitted.

        Returns
        -------
        int
            Numeric identifier assigned by the GLPI server.
        """

        response = await self._post_request(
            endpoint, model_to_payload(body_model), skip_entity=skip_entity
        )
        ensure_response_status(
            response,
            success_statuses=(200, 201),
            failure_message=failure_message,
        )
        new_id = require_response_int(
            response, keys=id_keys, missing_message=missing_message
        )
        logger.info("%s", log_message_factory(new_id))
        return new_id

    async def _resource_update(
        self,
        endpoint: str,
        body_model: GlpiModel,
        *,
        failure_message: str,
        log_message: str,
    ) -> None:
        """Patch one record and emit the standard log line on success.

        Parameters
        ----------
        endpoint : str
            Resource path forwarded to the transport ``PATCH`` helper.
        body_model : GlpiModel
            Partial Pydantic body serialised through
            :func:`model_to_payload`.
        failure_message : str
            Message embedded in the ``GlpiStatusError`` raised on a
            non-success HTTP status.
        log_message : str
            Pre-formatted message logged at ``INFO`` level on success.

        Returns
        -------
        None
        """

        response = await self._update_request(endpoint, model_to_payload(body_model))
        ensure_response_status(
            response,
            success_statuses=(200, 204),
            failure_message=failure_message,
        )
        logger.info("%s", log_message)

    async def _resource_delete(
        self,
        endpoint: str,
        *,
        failure_message: str,
        log_message: str,
        force: bool | None = None,
        delete_model_cls: type[GlpiModel] | None = None,
        body: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> None:
        """Delete one record and emit the standard log line on success.

        Parameters
        ----------
        endpoint : str
            Resource path forwarded to the transport ``DELETE`` helper.
        failure_message : str
            Message embedded in the ``GlpiStatusError`` raised on a
            non-success HTTP status.
        log_message : str
            Pre-formatted message logged at ``INFO`` level on success.
        force : bool | None, optional
            When ``True`` and ``delete_model_cls`` is provided, a
            ``{"force": True}`` body is sent to permanently delete the
            record. ``None`` omits the field altogether.
        delete_model_cls : type[GlpiModel] | None, optional
            Pydantic class instantiated with ``force`` to build the
            optional delete body.
        body : dict[str, object] | None, optional
            Pre-built request body forwarded as-is when supplied.
            Mutually exclusive with the ``force``/``delete_model_cls``
            pair.
        skip_entity : bool, optional
            When ``True`` the ``GLPI-Entity`` header is omitted.

        Returns
        -------
        None
        """

        request_body = body
        if request_body is None and delete_model_cls is not None and force is not None:
            request_body = model_to_payload(delete_model_cls(force=force))  # type: ignore[call-arg]
        response = await self._delete_request(
            endpoint, request_body, skip_entity=skip_entity
        )
        ensure_response_status(
            response,
            success_statuses=(200, 204),
            failure_message=failure_message,
        )
        logger.info("%s", log_message)


__all__ = ["TransportMixin"]
