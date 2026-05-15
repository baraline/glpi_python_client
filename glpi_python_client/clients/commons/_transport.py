"""Asynchronous GLPI v2 transport mixin.

The transport mixin owns token handling, header construction, retries, and
HTTP request dispatch so the per-endpoint mixins under
:mod:`glpi_python_client.clients.api` can stay focused on resource-specific
behaviour.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar, cast

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from glpi_python_client.clients.commons._http import (
    build_request_headers,
    build_request_url,
    ensure_response_status,
    finalize_request_response,
    list_payload_items,
    request_params,
    require_access_token,
    require_response_int,
    unwrap_timeline_items,
)
from glpi_python_client.clients.commons._payloads import (
    model_from_payload,
    model_to_payload,
)
from glpi_python_client.models._base import GlpiModel

if TYPE_CHECKING:
    from glpi_python_client.auth._v1_session import GLPIV1Session
    from glpi_python_client.auth.auth import GLPITokenManager

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=GlpiModel)


class AsyncTransportMixin:
    """Asynchronous GLPI API transport helpers shared by the API mixins.

    The class declares the runtime attributes the concrete client owns and
    exposes the awaitable ``_get_request``, ``_post_request``,
    ``_update_request`` and ``_delete_request`` helpers used by every
    per-endpoint mixin.
    """

    _auth: GLPITokenManager
    _auth_lock: asyncio.Lock
    _closed: bool = False
    _session: requests.Session
    _v1: GLPIV1Session | None
    entity_recursive: bool
    glpi_api_url: str
    glpi_entity: int | None
    glpi_profile: int | None
    language: str

    def _ensure_open(self) -> None:
        """Raise when the client has already been closed.

        All async transport helpers call this guard before touching the
        shared HTTP session so closed clients fail fast and predictably.
        """

        if self._closed:
            raise RuntimeError("GLPI client is closed")

    async def _ensure_token(self) -> None:
        """Ensure that a valid GLPI access token is available.

        Token refresh is serialised by the async lock so concurrent awaited
        calls do not race while updating shared authentication state.
        """

        self._ensure_open()
        async with self._auth_lock:
            await asyncio.to_thread(self._auth.ensure_token)

    async def _send_request(
        self,
        method: str,
        url: str,
        **kwargs: object,
    ) -> requests.Response:
        """Dispatch one blocking ``requests`` call from the async loop.

        The blocking HTTP call is wrapped in ``asyncio.to_thread`` so the
        async loop is never blocked by the underlying synchronous library.
        """

        request_method = getattr(self._session, method)
        return cast(
            requests.Response,
            await asyncio.to_thread(request_method, url, **kwargs),
        )

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
    ) -> requests.Response:
        """Execute one authenticated GLPI request asynchronously.

        The helper normalises the endpoint URL, headers, timeout, and
        payload placement before dispatching the blocking HTTP call through
        the async transport wrapper.
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

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_fixed(3),
    )
    async def _get_request(
        self,
        endpoint: str,
        params: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> requests.Response:
        """Execute one authenticated GLPI ``GET`` request asynchronously.

        Network-level request exceptions are retried according to the
        transport retry policy before the response is returned to the
        caller.
        """

        return await self._execute_request(
            method="get",
            endpoint=endpoint,
            success_statuses=(200, 206),
            params=params,
            skip_entity=skip_entity,
        )

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_fixed(3),
    )
    async def _post_request(
        self,
        endpoint: str,
        json_body: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> requests.Response:
        """Execute one authenticated GLPI ``POST`` request asynchronously.

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

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_fixed(3),
    )
    async def _update_request(
        self,
        endpoint: str,
        json_body: dict[str, object] | None = None,
    ) -> requests.Response:
        """Execute one authenticated GLPI ``PATCH`` request asynchronously.

        The helper uses the same authenticated execution path as the other
        HTTP verbs while targeting the success codes expected from update
        calls.
        """

        return await self._execute_request(
            method="patch",
            endpoint=endpoint,
            success_statuses=(200, 204),
            json_body=json_body,
            include_content_type=True,
        )

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_fixed(3),
    )
    async def _delete_request(
        self,
        endpoint: str,
        json_body: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> requests.Response:
        """Execute one authenticated GLPI ``DELETE`` request asynchronously.

        Some delete endpoints accept a JSON body, so the content-type header
        is enabled automatically when a body is supplied.
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
            When provided, response status is checked with this message;
            search-style endpoints that tolerate empty results pass
            ``None``.
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
        if failure_message is not None:
            ensure_response_status(
                response,
                success_statuses=success_statuses,
                failure_message=failure_message,
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
            Message embedded in the ``ValueError`` raised on a non-success
            HTTP status.
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
            Message embedded in the ``ValueError`` raised on a non-success
            HTTP status.
        missing_message : str
            Message embedded in the ``ValueError`` raised when the response
            payload does not contain any of the expected identifier keys.
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
            Message embedded in the ``ValueError`` raised on a non-success
            HTTP status.
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
            Message embedded in the ``ValueError`` raised on a non-success
            HTTP status.
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


__all__ = ["AsyncTransportMixin"]
