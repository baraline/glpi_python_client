"""Legacy GLPI v1 session management and document operations.

The high-level package still relies on selected v1 endpoints for document
upload and linking workflows, so this module owns the authenticated v1 HTTP
session and the retry logic around it.
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
    """Session manager for the GLPI v1 REST API.

    Parameters
    ----------
    base_url : str
        The v1 API base URL.
    user_token : str
        The ``user_token`` credential for v1 authentication.
    app_token : str
        The ``App-Token`` value.
    verify_ssl : bool, optional
        Whether to verify SSL certificates.
    session_refresh_interval_seconds : int, optional
        Maximum age of a v1 session token before it is renewed.
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
        """Call ``GET /initSession`` to obtain a session token.

        Returns
        -------
        None
            Stores the session token.

        Raises
        ------
        ValueError
            If the server does not return a valid session token.
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
        """Lazily initialise or renew the v1 session if needed.

        Returns
        -------
        None
            Ensures the session token exists.
        """

        if self._session_token is None:
            self._init_session()
            return
        if self._is_session_stale():
            logger.info("GLPI v1 session reached refresh interval; renewing session.")
            self._renew_session()

    def _is_session_stale(self) -> bool:
        """Return whether the current v1 session should be renewed.

        Returns
        -------
        bool
            ``True`` when the session age is beyond the configured refresh
            interval.
        """

        if self._session_started_at is None:
            return True
        return datetime.now(tz=timezone.utc) >= (
            self._session_started_at + self._session_refresh_interval
        )

    def _session_headers(self) -> dict[str, str]:
        """Return headers for the current v1 session token.

        Returns
        -------
        dict[str, str]
            Headers including the current session token.
        """

        headers: dict[str, str] = {
            "Session-Token": str(self._session_token),
            "Accept": "application/json",
        }
        if self._app_token:
            headers["App-Token"] = self._app_token
        return headers

    def _renew_session(self) -> None:
        """Close the current v1 session token and initialise a new one.

        Returns
        -------
        None
            Mutates the stored session token.
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
        """Return headers for an authenticated v1 request.

        Returns
        -------
        dict[str, str]
            Headers including the session token.
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
        """Execute one v1 request and retry once after auth rejection.

        Parameters
        ----------
        method : str
            HTTP method.
        url : str
            Absolute request URL.
        headers : dict[str, str] | None, optional
            Additional request headers.
        **kwargs : object
            Additional ``requests`` keyword arguments.

        Returns
        -------
        requests.Response
            Raw response from GLPI.
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

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(3))
    def get_sub_items(
        self,
        itemtype: str,
        item_id: str | int,
        sub_itemtype: str,
    ) -> list[dict[str, object]]:
        """Fetch legacy GLPI sub-items for one parent item.

        Parameters
        ----------
        itemtype : str
            Parent GLPI itemtype.
        item_id : str | int
            Parent item identifier.
        sub_itemtype : str
            Child itemtype to fetch.

        Returns
        -------
        list[dict[str, object]]
            Raw sub-item payloads.

        Raises
        ------
        ValueError
            If the request fails or returns an unexpected payload shape.
        """

        response = self._authenticated_request(
            "GET",
            f"{self._base_url}/{itemtype}/{item_id}/{sub_itemtype}",
            timeout=30,
        )
        if response.status_code not in (200, 206):
            raise ValueError(
                "GLPI v1 sub-item fetch failed: "
                f"{response.status_code} {response.text[:300]}"
            )

        payload = response.json()
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            return [payload]
        raise ValueError(
            "GLPI v1 sub-item fetch returned unexpected payload: "
            f"{type(payload).__name__}"
        )

    def close(self) -> None:
        """Kill the v1 session and release resources.

        Returns
        -------
        None
            Best-effort cleanup.
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
        """Upload a document via ``POST /Document``.

        Parameters
        ----------
        filename : str
            File name.
        content : bytes
            Raw file bytes.
        mime_type : str
            MIME type.
        document_name : str | None, optional
            GLPI display name.
        ticket_id : int | None, optional
            GLPI ticket ID used to link the document during creation.
        entity_id : int | None, optional
            GLPI entity ID assigned to the created document.

        Returns
        -------
        dict[str, object]
            GLPI response payload.

        Raises
        ------
        ValueError
            If upload fails.
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

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(3))
    def link_document_to_ticket(
        self, document_id: int, ticket_id: int
    ) -> dict[str, object]:
        """Link an existing document to a ticket.

        Parameters
        ----------
        document_id : int
            GLPI document ID.
        ticket_id : int
            GLPI ticket ID.

        Returns
        -------
        dict[str, object]
            GLPI response payload.

        Raises
        ------
        ValueError
            If the link creation fails.
        """

        payload = json.dumps(
            {
                "input": {
                    "documents_id": document_id,
                    "itemtype": "Ticket",
                    "items_id": ticket_id,
                }
            }
        )
        response = self._authenticated_request(
            "POST",
            f"{self._base_url}/Document_Item",
            headers={"Content-Type": "application/json"},
            data=payload,
            timeout=30,
        )
        if response.status_code not in (200, 201):
            raise ValueError(
                "GLPI v1 Document_Item link failed: "
                f"{response.status_code} {response.text[:300]}"
            )
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError(
                "GLPI v1 Document_Item link returned unexpected payload: "
                f"{type(result).__name__}"
            )
        logger.info("GLPI v1 document %d linked to ticket %d", document_id, ticket_id)
        return cast(dict[str, object], result)


def _is_auth_failure_response(response: requests.Response) -> bool:
    """Return whether one GLPI v1 response means the session is invalid.

    Parameters
    ----------
    response : requests.Response
        Raw GLPI response.

    Returns
    -------
    bool
        ``True`` when the response indicates an expired or rejected v1 session.
    """

    if response.status_code in _AUTH_FAILURE_STATUS_CODES:
        return True
    return "ERROR_SESSION_TOKEN_INVALID" in str(response.text or "")
