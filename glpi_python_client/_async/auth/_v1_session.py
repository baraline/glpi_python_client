"""GLPI v1 REST session used for legacy endpoints not exposed by v2.

Two consumers currently share this session:

* the management :class:`DocumentMixin` for the multipart
  ``POST /Document`` upload (the v2 API does not advertise a binary
  upload route), and
* the :class:`PluginFieldsMixin` for the GLPI "Fields" plugin endpoints
  (``PluginFieldsContainer``, ``PluginFieldsField`` and the per-item
  value itemtypes), which the v2 contract does not surface at all.

The session wrapper owns the authenticated v1 lifecycle (init, refresh,
kill) and exposes the typed ``upload_document`` helper plus the generic
``request_json`` JSON-only HTTP helper that newer mixins build on.

Retry policy
------------
Every public dispatch helper (``_init_session``, ``request_json``,
``upload_document``) carries the same :mod:`tenacity` retry decorator
used by the v2 transport: three attempts spaced by three seconds,
triggered by :class:`~glpi_python_client.GlpiTransportError` (network
faults) and
:class:`~glpi_python_client.GlpiServerError` (which
:func:`finalize_request_response` raises for 5xx server errors), with
``reraise=True`` so the real error surfaces once retries are exhausted.
Not every :class:`ValueError` subclass is retried, only the one named in
the predicate above: :class:`~glpi_python_client.GlpiServerError` (5xx)
*is* a ``ValueError`` and *is* retried by this decorator.
:class:`~glpi_python_client.GlpiStatusError` subclasses for 4xx statuses,
:class:`~glpi_python_client.GlpiValidationError`, and
:class:`~glpi_python_client.GlpiProtocolError` are also ``ValueError``
subclasses but are not in the retry predicate, so they surface
immediately without a retry.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from glpi_python_client._async.clients.commons._config import build_http_session
from glpi_python_client._async.clients.commons._http import (
    ensure_response_status,
    finalize_request_response,
    response_json_or_empty,
    transport_error_from,
)
from glpi_python_client._errors import (
    GlpiProtocolError,
    GlpiServerError,
    GlpiTransportError,
    GlpiValidationError,
)

logger = logging.getLogger(__name__)

_DEFAULT_SESSION_REFRESH_INTERVAL_SECONDS = 15 * 60
_AUTH_FAILURE_STATUS_CODES = frozenset({401, 403})
#: Retry policy for the v1 session, expressed in library-owned types.
#:
#: Mirrors the v2 transport policy deliberately: naming the HTTP library's
#: own exception base here would make the retries stop matching — silently —
#: the next time the transport changes.
_RETRY_ON_NETWORK_ERRORS = retry(
    retry=retry_if_exception_type((GlpiTransportError, GlpiServerError)),
    stop=stop_after_attempt(3),
    wait=wait_fixed(3),
    reraise=True,
)


class GLPIV1Session:
    """Authenticated GLPI v1 REST session limited to document upload.

    The session takes care of token initialisation, periodic refresh, retry on
    auth failure, and best-effort cleanup. Only the upload endpoint is exposed
    because the rest of the high-level client uses the v2 API exclusively.
    """

    def __init__(
        self,
        *,
        base_url: str,
        user_token: str,
        app_token: str | None = None,
        verify_ssl: bool = True,
        session_refresh_interval_seconds: int = (
            _DEFAULT_SESSION_REFRESH_INTERVAL_SECONDS
        ),
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._user_token = user_token
        self._app_token = app_token
        if session_refresh_interval_seconds < 1:
            raise GlpiValidationError(
                "session_refresh_interval_seconds must be a positive integer"
            )
        self._session_refresh_interval = timedelta(
            seconds=session_refresh_interval_seconds
        )

        # Built through the shared factory so the SSL policy is applied at
        # construction: httpx reads ``verify`` only in ``Client.__init__``
        # and silently ignores a later assignment.
        self._http = build_http_session(verify_ssl=verify_ssl)

        self._session_token: str | None = None
        self._session_started_at: datetime | None = None

    async def _dispatch(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send one raw v1 HTTP call, translating transport faults.

        Every call this session makes goes through here so network failures
        surface as :class:`~glpi_python_client.GlpiTransportError` rather than
        as the HTTP library's own exception type. That is what lets the retry
        predicate above name a library-owned type, and it keeps callers from
        having to import the HTTP library to catch a connection failure.

        Raises
        ------
        GlpiTransportError
            When the request never produced a response.
        """

        try:
            return await self._http.request(method.upper(), url, **kwargs)
        except httpx.HTTPError as exc:
            raise transport_error_from(exc, method=method, url=url) from exc

    @_RETRY_ON_NETWORK_ERRORS
    async def _init_session(self) -> None:
        """Acquire one fresh GLPI v1 session token via ``GET /initSession``.

        The call replaces any existing session state and stores the
        authentication timestamp used by the refresh-interval check.
        Network errors and 5xx responses are retried; 4xx and payload
        errors propagate immediately as :class:`ValueError`.
        """

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"user_token {self._user_token}",
        }
        if self._app_token:
            headers["App-Token"] = self._app_token

        url = f"{self._base_url}/initSession"
        response = await self._dispatch("GET", url, headers=headers, timeout=30)
        finalize_request_response(
            response,
            method="get",
            url=url,
            success_statuses=(200,),
            logger=logger,
        )
        ensure_response_status(
            response,
            success_statuses=(200,),
            failure_message="GLPI v1 initSession failed",
        )

        token = response.json().get("session_token")
        if not token:
            raise GlpiProtocolError("GLPI v1 initSession returned no session_token")

        self._session_token = str(token)
        self._session_started_at = datetime.now(tz=timezone.utc)
        logger.info("GLPI v1 session initialised.")

    async def _ensure_session(self) -> None:
        """Lazily initialise or renew the v1 session when the token is stale.

        The helper is called by every authenticated request before any header
        construction so callers never have to manage the lifecycle directly.
        """

        if self._session_token is None:
            await self._init_session()
            return
        if self._is_session_stale():
            logger.info("GLPI v1 session reached refresh interval; renewing session.")
            await self._renew_session()

    def _is_session_stale(self) -> bool:
        """Return whether the current v1 session token must be renewed.

        Stale tokens are determined by the configured refresh interval relative
        to the timestamp the current token was acquired.
        """

        if self._session_started_at is None:
            return True
        return datetime.now(tz=timezone.utc) >= (
            self._session_started_at + self._session_refresh_interval
        )

    def _session_headers(self) -> dict[str, str]:
        """Return the GLPI v1 headers carrying the current session token.

        The helper assumes ``_ensure_session`` has already been called so the
        session token state is valid.
        """

        headers: dict[str, str] = {
            "Session-Token": str(self._session_token),
            "Accept": "application/json",
        }
        if self._app_token:
            headers["App-Token"] = self._app_token
        return headers

    async def _renew_session(self) -> None:
        """Drop the current GLPI v1 session token and acquire a new one.

        The previous token is best-effort killed so the GLPI server can release
        the associated session state immediately. ``_init_session`` will set
        the new token on success or raise, leaving the existing state
        untouched on failure (the retry decorator handles transients).
        """

        if self._session_token is not None:
            try:
                await self._dispatch(
                    "GET",
                    f"{self._base_url}/killSession",
                    headers=self._session_headers(),
                    timeout=10,
                )
            except Exception:
                logger.warning("Failed to kill stale GLPI v1 session.", exc_info=True)
        await self._init_session()

    async def _headers(self) -> dict[str, str]:
        """Return ready-to-use authenticated GLPI v1 request headers.

        The helper is the single header entry-point used by all authenticated
        v1 calls so token lifecycle handling stays centralised.
        """

        await self._ensure_session()
        return self._session_headers()

    async def _authenticated_request(
        self,
        method: str,
        url: str,
        *,
        success_statuses: tuple[int, ...],
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send one authenticated GLPI v1 request and finalize the response.

        When the GLPI server rejects the current token the helper renews
        the session and retries the request once. The returned response
        has already been passed through :func:`finalize_request_response`
        so 5xx errors surface as
        :class:`~glpi_python_client.GlpiServerError` for the outer
        tenacity retry to catch; non-success statuses outside the
        ``success_statuses`` set are logged but otherwise returned for
        the caller to validate with :func:`ensure_response_status`.
        """

        request_headers = {**await self._headers(), **(headers or {})}
        # Dispatch through ``request(method, ...)`` rather than looking up a
        # per-verb attribute: it is the one call shape both transports share,
        # and it keeps the verb a value instead of an attribute name.
        verb = method.upper()
        response = await self._dispatch(verb, url, headers=request_headers, **kwargs)
        if _is_auth_failure_response(response):
            logger.warning(
                "GLPI v1 session token was rejected; refreshing session and "
                "retrying request once."
            )
            await self._renew_session()
            request_headers = {**await self._headers(), **(headers or {})}
            response = await self._dispatch(
                verb, url, headers=request_headers, **kwargs
            )
        return finalize_request_response(
            response,
            method=method,
            url=url,
            success_statuses=success_statuses,
            logger=logger,
        )

    async def close(self) -> None:
        """Kill the v1 session token and release the underlying HTTP session.

        Cleanup is best-effort: any failure during ``killSession`` is logged
        and the local session state is still cleared.
        """

        try:
            if self._session_token is not None:
                await self._dispatch(
                    "GET",
                    f"{self._base_url}/killSession",
                    headers=self._session_headers(),
                    timeout=10,
                )
                logger.info("GLPI v1 session killed.")
        except Exception:
            logger.warning("Failed to kill GLPI v1 session.", exc_info=True)
        finally:
            self._session_token = None
            self._session_started_at = None
            await self._http.aclose()

    @_RETRY_ON_NETWORK_ERRORS
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
        """Send one JSON-only authenticated request to the GLPI v1 API.

        The helper centralises session-token handling, the one-shot retry
        on token rejection, status validation and JSON parsing so callers
        can stay focused on their endpoint semantics. Network errors and
        5xx responses are retried; 4xx and payload errors propagate
        immediately as :class:`ValueError`.

        Parameters
        ----------
        method : str
            HTTP verb (``"GET"``, ``"POST"``, ``"PUT"``, ``"DELETE"``).
        path : str
            Resource path appended to the v1 base URL (without leading
            slash, e.g. ``"PluginFieldsContainer"``).
        params : dict[str, object] | None, optional
            Query-string parameters forwarded to the HTTP transport.
        json_body : dict[str, object] | None, optional
            JSON body serialised into the request when set. The
            ``Content-Type: application/json`` header is added
            automatically.
        success_statuses : tuple[int, ...], optional
            HTTP status codes considered successful (default covers the
            CRUD codes returned by the v1 API).
        failure_message : str | None, optional
            Prefix used in the :class:`~glpi_python_client.GlpiStatusError`
            raised on a non-success status. Defaults to ``"GLPI v1
            {METHOD} {path} failed"``.

        Returns
        -------
        object
            Parsed JSON body for non-empty responses; an empty ``dict``
            when the body is empty or contains only whitespace.

        Raises
        ------
        GlpiStatusError
            If the v1 server returns a non-success HTTP status outside
            the 5xx range (narrows to :class:`~glpi_python_client.GlpiAuthError`
            or :class:`~glpi_python_client.GlpiNotFoundError` where the
            status allows it). Inherits from ``ValueError``.
        GlpiServerError
            If the v1 server persistently returns a 5xx status after this
            decorator's retries are exhausted.
        """

        url = f"{self._base_url}/{path.lstrip('/')}"
        kwargs: dict[str, Any] = {"timeout": 30}
        if params is not None:
            kwargs["params"] = params
        headers: dict[str, str] = {}
        if json_body is not None:
            kwargs["content"] = json.dumps(json_body)
            headers["Content-Type"] = "application/json"
        response = await self._authenticated_request(
            method,
            url,
            success_statuses=success_statuses,
            headers=headers or None,
            **kwargs,
        )
        ensure_response_status(
            response,
            success_statuses=success_statuses,
            failure_message=failure_message
            or f"GLPI v1 {method.upper()} {path} failed",
        )
        return response_json_or_empty(response)

    @_RETRY_ON_NETWORK_ERRORS
    async def upload_document(
        self,
        filename: str,
        content: bytes,
        mime_type: str,
        *,
        document_name: str | None = None,
        ticket_id: int | None = None,
        entity_id: int | None = None,
    ) -> dict[str, object]:
        """Upload one binary document via ``POST /Document``.

        The legacy v1 endpoint uses a multipart upload manifest so the GLPI
        server can create the document, link it to the optional parent ticket,
        and assign it to the provided entity in a single round-trip. Network
        errors and 5xx responses are retried; 4xx and payload errors
        propagate immediately as :class:`ValueError`.
        """

        manifest_input: dict[str, object] = {
            "name": document_name or filename,
            "_filename": [filename],
        }
        if entity_id is not None:
            manifest_input["entities_id"] = int(entity_id)
        if ticket_id is not None:
            manifest_input["itemtype"] = "Ticket"
            manifest_input["items_id"] = int(ticket_id)
            manifest_input["tickets_id"] = int(ticket_id)
        manifest = json.dumps({"input": manifest_input})
        response = await self._authenticated_request(
            "POST",
            f"{self._base_url}/Document",
            success_statuses=(200, 201),
            files=[
                ("uploadManifest", (None, manifest, "application/json")),
                ("filename[]", (filename, content, mime_type)),
            ],
            timeout=60,
        )
        ensure_response_status(
            response,
            success_statuses=(200, 201),
            failure_message="GLPI v1 document upload failed",
        )
        payload = response.json()
        if not isinstance(payload, dict):
            raise GlpiProtocolError(
                "GLPI v1 document upload returned unexpected payload: "
                f"{type(payload).__name__}"
            )
        logger.info("GLPI v1 document uploaded: id=%s", payload.get("id"))
        return cast(dict[str, object], payload)


def _is_auth_failure_response(response: httpx.Response) -> bool:
    """Return whether one GLPI v1 response means the session token is invalid.

    Both HTTP-level rejection and the ``ERROR_SESSION_TOKEN_INVALID`` payload
    marker emitted by the GLPI v1 API are considered auth failures.
    """

    if response.status_code in _AUTH_FAILURE_STATUS_CODES:
        return True
    return "ERROR_SESSION_TOKEN_INVALID" in str(response.text or "")


__all__ = ["GLPIV1Session"]
