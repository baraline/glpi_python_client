"""OAuth2 token management for the high-level GLPI clients.

The token manager centralizes credential validation, token acquisition,
refresh behavior, and lifecycle cleanup so both sync and async clients can
share the same authenticated session state.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from glpi_python_client._errors import (
    GlpiServerError,
    GlpiValidationError,
    status_error_class,
)

logger = logging.getLogger(__name__)


class GLPITokenManager:
    """OAuth2 token manager for the GLPI API.

    Parameters
    ----------
    token_url : str
        Full URL of the GLPI token endpoint.
    client_id : str | None, optional
        OAuth2 client ID. Provide it together with ``client_secret`` when the
        GLPI instance requires client authentication.
    client_secret : str | None, optional
        OAuth2 client secret. Provide it together with ``client_id``.
    username : str | None, optional
        Username for the password grant flow. Provide it together with
        ``password``.
    password : str | None, optional
        Password for the password grant flow. Provide it together with
        ``username``.
    session : requests.Session | None, optional
        Existing session to reuse.
    auth_token_refresh : int | None, optional
        Maximum token age in seconds before a refresh is attempted. ``None``
        disables interval-based refreshes.
    """

    def __init__(
        self,
        token_url: str,
        client_id: str | None = None,
        client_secret: str | None = None,
        username: str | None = None,
        password: str | None = None,
        session: requests.Session | None = None,
        auth_token_refresh: int | None = None,
    ) -> None:
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._username = username
        self._password = password
        self._owns_session = session is None
        self._session = session or requests.Session()
        self._auth_token_refresh_interval = _refresh_interval(auth_token_refresh)

        self._validate_credentials()

        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.token_expires_at: datetime | None = None
        self.token_updated_at: datetime | None = None

    @property
    def auth_token_refresh(self) -> int | None:
        """Return the proactive refresh delay configured for this manager.

        The public property keeps the original integer value used at
        construction time instead of exposing the internal ``timedelta``
        representation.
        """

        if self._auth_token_refresh_interval is None:
            return None
        return int(self._auth_token_refresh_interval.total_seconds())

    def _validate_credentials(self) -> None:
        """Validate that the configured OAuth credential sets are complete.

        GLPI authentication supports either client credentials, user
        credentials, or both together. Partial pairs are rejected here so the
        token request path does not fail later with a less actionable error.
        """

        missing_client_fields = [
            name
            for name, value in {
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            }.items()
            if value is None
        ]
        missing_user_fields = [
            name
            for name, value in {
                "username": self._username,
                "password": self._password,
            }.items()
            if value is None
        ]

        has_client_fields = len(missing_client_fields) < 2
        has_user_fields = len(missing_user_fields) < 2

        if has_client_fields and missing_client_fields:
            raise GlpiValidationError(
                "GLPI OAuth client credentials must include both client_id "
                "and client_secret."
            )
        if has_user_fields and missing_user_fields:
            raise GlpiValidationError(
                "GLPI user credentials must include both username and password."
            )
        if not self._has_client_credentials and not self._has_user_credentials:
            raise GlpiValidationError(
                "GLPI authentication requires either client_id/client_secret, "
                "username/password, or both."
            )

    @property
    def _has_client_credentials(self) -> bool:
        return self._client_id is not None and self._client_secret is not None

    @property
    def _has_user_credentials(self) -> bool:
        return self._username is not None and self._password is not None

    def _build_token_request_data(self) -> dict[str, str]:
        """Build the form payload sent to the OAuth token endpoint.

        The payload shape depends on whether the manager is using the password
        grant or pure client-credentials flow, and it includes client
        credentials when that pair is configured.
        """

        data: dict[str, str] = {"scope": "api"}
        if self._has_user_credentials:
            assert self._username is not None
            assert self._password is not None
            data["grant_type"] = "password"
            data["username"] = self._username
            data["password"] = self._password
        else:
            data["grant_type"] = "client_credentials"

        if self._has_client_credentials:
            assert self._client_id is not None
            assert self._client_secret is not None
            data["client_id"] = self._client_id
            data["client_secret"] = self._client_secret

        return data

    def _store_token_data(
        self, token_data: dict[str, object], label: str = "acquired"
    ) -> None:
        """Store token data from an OAuth2 response.

        Parameters
        ----------
        token_data : dict[str, object]
            Token endpoint JSON response.
        label : str, optional
            Label for log messages.

        Returns
        -------
        None
            Mutates instance state.
        """

        self.access_token = str(token_data.get("access_token") or "") or None
        refresh_token = str(token_data.get("refresh_token") or "").strip()
        if refresh_token:
            self.refresh_token = refresh_token
        expires_in = int(str(token_data.get("expires_in") or 3600))
        now = datetime.now(tz=timezone.utc)
        self.token_updated_at = now
        self.token_expires_at = now + timedelta(seconds=expires_in)
        logger.info("GLPI OAuth token %s successfully.", label)

    def logout(self) -> None:
        """Discard the currently cached OAuth tokens.

        Returns
        -------
        None
            Clears in-memory token state.
        """

        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        self.token_updated_at = None

    def close(self) -> None:
        """Release token-manager resources.

        Returns
        -------
        None
            Performs a local logout and closes any owned HTTP session.
        """

        self.logout()
        if self._owns_session:
            self._session.close()

    def _should_refresh_by_interval(self, now: datetime) -> bool:
        """Return whether the configured proactive refresh interval elapsed.

        This check supplements token-expiry handling so long-lived clients can
        refresh credentials before the server-side expiry timestamp is reached.
        """

        if self._auth_token_refresh_interval is None or self.token_updated_at is None:
            return False
        return now >= self.token_updated_at + self._auth_token_refresh_interval

    @retry(
        retry=retry_if_exception_type((requests.RequestException, GlpiServerError)),
        stop=stop_after_attempt(3),
        wait=wait_fixed(3),
        reraise=True,
    )
    def _acquire_token(self) -> None:
        """Acquire an OAuth2 access token using the configured auth flow.

        Returns
        -------
        None
            Stores the new access token.

        Raises
        ------
        GlpiAuthError
            If GLPI rejects the credentials (401/403). Not retried.
        GlpiServerError
            If the token endpoint fails (5xx). Retried up to 3 attempts.
        GlpiStatusError
            If the token endpoint returns any other unexpected status. Not
            retried.
        """

        data = self._build_token_request_data()
        response = self._session.post(self._token_url, data=data, timeout=30)
        if 200 <= response.status_code < 300:
            self._store_token_data(response.json())
            return
        try:
            error_detail = response.json()
        except Exception:
            error_detail = response.text
        error_class = status_error_class(response.status_code)
        raise error_class(
            f"GLPI OAuth token returned {response.status_code}: {error_detail}",
            status_code=response.status_code,
            url=self._token_url,
            response_text=str(error_detail),
        )

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_fixed(3),
        reraise=True,
    )
    def _refresh_access_token(self) -> None:
        """Refresh the OAuth2 access token using the stored refresh token.

        Returns
        -------
        None
            Stores the refreshed token or acquires a new one.

        Raises
        ------
        GlpiAuthError
            If GLPI rejects the credentials while refreshing (401/403). This
            method does not raise directly on a non-2xx response: it logs a
            warning and falls through to a nested :meth:`_acquire_token`
            call, which raises. That nested call is not retried by either
            decorator, so a persistent 401 costs 1 refresh POST + 1 acquire
            POST (2 total) before this propagates.
        GlpiServerError
            If the token endpoint fails (5xx) while refreshing. This
            method's own retry decorator only matches
            ``requests.RequestException`` (network-level faults), not
            ``GlpiServerError``, so it does not retry the fall-through to
            :meth:`_acquire_token`. The nested call carries its own
            independent decorator, which does retry ``GlpiServerError`` up
            to 3 attempts. A persistent 5xx therefore costs exactly 1
            refresh POST + 3 nested acquire POSTs = 4 POST requests, not the
            12 an earlier, less precise predicate produced by retrying the
            already-retried nested failure a second time.
        GlpiStatusError
            If the token endpoint returns any other unexpected status while
            refreshing, raised by the nested :meth:`_acquire_token` call.
            Not retried.
        """

        if not self.refresh_token:
            self._acquire_token()
            return

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        if self._has_client_credentials:
            assert self._client_id is not None
            assert self._client_secret is not None
            data["client_id"] = self._client_id
            data["client_secret"] = self._client_secret
        response = self._session.post(self._token_url, data=data, timeout=30)
        if 200 <= response.status_code < 300:
            self._store_token_data(response.json(), label="refreshed")
            return
        logger.warning("Token refresh failed, acquiring new token...")
        self._acquire_token()

    def ensure_token(self) -> None:
        """Ensure a valid OAuth2 access token is available.

        Returns
        -------
        None
            Updates token state when needed.
        """

        if not self.access_token:
            self._acquire_token()
            return

        now = datetime.now(tz=timezone.utc)
        token_expired = (
            self.token_expires_at is not None and now >= self.token_expires_at
        )
        if token_expired or self._should_refresh_by_interval(now):
            self._refresh_access_token()


def _refresh_interval(value: int | None) -> timedelta | None:
    if value is None:
        return None
    if value < 1:
        raise GlpiValidationError(
            "auth_token_refresh must be a positive integer or None"
        )
    return timedelta(seconds=value)
