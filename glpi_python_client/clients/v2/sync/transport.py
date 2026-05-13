"""Synchronous GLPI v2 transport methods.

This module owns the authenticated ``requests`` call helpers used by the sync
mixins to communicate with the GLPI high-level API.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from glpi_python_client.clients.v2.common.request_http import (
    build_request_headers,
    build_request_url,
    finalize_request_response,
    request_params,
    require_access_token,
)

if TYPE_CHECKING:
    from glpi_python_client.auth.auth import GLPITokenManager
    from glpi_python_client.clients.api_v1_session import GLPIV1Session

logger = logging.getLogger(__name__)


class SyncTransportMixin:
    """Synchronous GLPI API transport helpers.

    The transport mixin keeps token handling, header construction, retries, and
    request dispatch out of the endpoint-specific synchronous mixins.
    """

    _auth: GLPITokenManager
    _auth_lock: Any
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

        All synchronous transport helpers call this guard before touching the
        shared HTTP session.
        """

        if self._closed:
            raise RuntimeError("GLPI client is closed")

    def _ensure_token(self) -> None:
        """Ensure that a valid GLPI access token is available.

        Token refresh is protected by the client lock so concurrent sync calls
        do not race while updating shared authentication state.
        """

        self._ensure_open()
        with self._auth_lock:
            self._auth.ensure_token()

    def _get_headers(
        self,
        *,
        include_content_type: bool = False,
        skip_entity: bool = False,
    ) -> dict[str, str]:
        """Build GLPI request headers for the current client state.

        This convenience wrapper forwards the current transport state to the
        shared header builder used across sync and async implementations.
        """

        return build_request_headers(
            access_token=self._auth.access_token,
            language=self.language,
            glpi_entity=self.glpi_entity,
            glpi_profile=self.glpi_profile,
            entity_recursive=self.entity_recursive,
            include_content_type=include_content_type,
            skip_entity=skip_entity,
        )

    def _send_request(
        self,
        method: str,
        url: str,
        **kwargs: object,
    ) -> requests.Response:
        request_method = getattr(self._session, method)
        return cast(requests.Response, request_method(url, **kwargs))

    def _execute_request(
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
        """Execute one authenticated GLPI request.

        The helper normalizes the endpoint URL, headers, timeout, and payload
        placement before handing the response to the shared validation logic.
        """

        self._ensure_token()
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

        response = self._send_request(method, url, **request_kwargs)
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
    def _get_request(
        self,
        endpoint: str,
        params: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> requests.Response:
        """Execute one authenticated GLPI ``GET`` request.

        Network-level request exceptions are retried according to the transport
        retry policy before the response is returned to the caller.
        """

        return self._execute_request(
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
    def _post_request(
        self,
        endpoint: str,
        json_body: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> requests.Response:
        """Execute one authenticated GLPI ``POST`` request.

        JSON request bodies automatically include the content-type header needed
        by the GLPI API.
        """

        return self._execute_request(
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
    def _update_request(
        self,
        endpoint: str,
        json_body: dict[str, object] | None = None,
    ) -> requests.Response:
        """Execute one authenticated GLPI ``PATCH`` request.

        The helper uses the same authenticated execution path as the other HTTP
        verbs while targeting the success codes expected from update calls.
        """

        return self._execute_request(
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
    def _delete_request(
        self,
        endpoint: str,
        json_body: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> requests.Response:
        """Execute one authenticated GLPI ``DELETE`` request.

        Some delete endpoints accept a JSON body, so the content-type header is
        enabled automatically when a body is supplied.
        """

        return self._execute_request(
            method="delete",
            endpoint=endpoint,
            success_statuses=(200, 204),
            json_body=json_body,
            skip_entity=skip_entity,
            include_content_type=json_body is not None,
        )
