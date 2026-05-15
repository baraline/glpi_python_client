"""GLPI v1 REST session used exclusively for document uploads.

The high-level async ``GlpiClient`` only relies on the legacy v1 API for the
``POST /Document`` multipart upload endpoint. The session wrapper below owns
the authenticated v1 lifecycle (init, refresh, kill) and exposes a single
``upload_document`` operation that the management mixin calls through
``asyncio.to_thread`` at the blocking HTTP boundary.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import cast

import requests
from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)

_DEFAULT_SESSION_REFRESH_INTERVAL_SECONDS = 15 * 60
_AUTH_FAILURE_STATUS_CODES = frozenset({401, 403})


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
        app_token: str,
        verify_ssl: bool = True,
        session_refresh_interval_seconds: int = (
            _DEFAULT_SESSION_REFRESH_INTERVAL_SECONDS
        ),
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._user_token = user_token
        self._app_token = app_token
        if session_refresh_interval_seconds < 1:
            raise ValueError(
                "session_refresh_interval_seconds must be a positive integer"
            )
        self._session_refresh_interval = timedelta(
            seconds=session_refresh_interval_seconds
        )

        self._http = requests.Session()
        self._http.verify = verify_ssl

        self._session_token: str | None = None
        self._session_started_at: datetime | None = None

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(3))
    def _init_session(self) -> None:
        """Acquire one fresh GLPI v1 session token via ``GET /initSession``.

        The call replaces any existing session state and stores the
        authentication timestamp used by the refresh-interval check.
        """

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"user_token {self._user_token}",
        }
        if self._app_token:
            headers["App-Token"] = self._app_token

        response = self._http.get(
            f"{self._base_url}/initSession",
            headers=headers,
            timeout=30,
        )
        if response.status_code != 200:
            raise ValueError(
                "GLPI v1 initSession failed: "
                f"{response.status_code} {response.text[:300]}"
            )

        token = response.json().get("session_token")
        if not token:
            raise ValueError("GLPI v1 initSession returned no session_token")

        self._session_token = str(token)
        self._session_started_at = datetime.now(tz=timezone.utc)
        logger.info("GLPI v1 session initialised.")

    def _ensure_session(self) -> None:
        """Lazily initialise or renew the v1 session when the token is stale.

        The helper is called by every authenticated request before any header
        construction so callers never have to manage the lifecycle directly.
        """

        if self._session_token is None:
            self._init_session()
            return
        if self._is_session_stale():
            logger.info("GLPI v1 session reached refresh interval; renewing session.")
            self._renew_session()

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

    def _renew_session(self) -> None:
        """Drop the current GLPI v1 session token and acquire a new one.

        The previous token is best-effort killed so the GLPI server can release
        the associated session state immediately.
        """

        old_token = self._session_token
        if old_token is not None:
            try:
                self._http.get(
                    f"{self._base_url}/killSession",
                    headers=self._session_headers(),
                    timeout=10,
                )
            except Exception:
                logger.warning("Failed to kill stale GLPI v1 session.", exc_info=True)
        self._session_token = None
        self._session_started_at = None
        self._init_session()

    def _headers(self) -> dict[str, str]:
        """Return ready-to-use authenticated GLPI v1 request headers.

        The helper is the single header entry-point used by all authenticated
        v1 calls so token lifecycle handling stays centralised.
        """

        self._ensure_session()
        return self._session_headers()

    def _authenticated_request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        **kwargs: object,
    ) -> requests.Response:
        """Send one authenticated GLPI v1 request with one auth-failure retry.

        When the GLPI server rejects the current token, the helper renews the
        session and retries the request once before returning the response.
        """

        request_headers = {**self._headers(), **(headers or {})}
        request_method = getattr(self._http, method.lower())
        response = cast(
            requests.Response,
            request_method(url, headers=request_headers, **kwargs),
        )
        if not _is_auth_failure_response(response):
            return response

        logger.warning(
            "GLPI v1 session token was rejected; refreshing session and retrying "
            "request once."
        )
        self._renew_session()
        request_headers = {**self._headers(), **(headers or {})}
        return cast(
            requests.Response,
            request_method(url, headers=request_headers, **kwargs),
        )

    def close(self) -> None:
        """Kill the v1 session token and release the underlying HTTP session.

        Cleanup is best-effort: any failure during ``killSession`` is logged
        and the local session state is still cleared.
        """

        try:
            if self._session_token is not None:
                self._http.get(
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
            self._http.close()

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(3))
    def upload_document(
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
        and assign it to the provided entity in a single round-trip.
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
        response = self._authenticated_request(
            "POST",
            f"{self._base_url}/Document",
            files=[
                ("uploadManifest", (None, manifest, "application/json")),
                ("filename[]", (filename, content, mime_type)),
            ],
            timeout=60,
        )
        if response.status_code not in (200, 201):
            raise ValueError(
                "GLPI v1 document upload failed: "
                f"{response.status_code} {response.text[:300]}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(
                "GLPI v1 document upload returned unexpected payload: "
                f"{type(payload).__name__}"
            )
        logger.info("GLPI v1 document uploaded: id=%s", payload.get("id"))
        return cast(dict[str, object], payload)


def _is_auth_failure_response(response: requests.Response) -> bool:
    """Return whether one GLPI v1 response means the session token is invalid.

    Both HTTP-level rejection and the ``ERROR_SESSION_TOKEN_INVALID`` payload
    marker emitted by the GLPI v1 API are considered auth failures.
    """

    if response.status_code in _AUTH_FAILURE_STATUS_CODES:
        return True
    return "ERROR_SESSION_TOKEN_INVALID" in str(response.text or "")


__all__ = ["GLPIV1Session"]
