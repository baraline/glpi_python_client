from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import cast

import pytest
import requests
from tenacity import wait_fixed

from glpi_python_client import GlpiAuthError, GlpiServerError
from glpi_python_client.auth.auth import GLPITokenManager
from glpi_python_client.testing.utils import FakeResponse, TokenResponse


class _FakeSession:
    def __init__(self, response: FakeResponse | None = None):
        self.response = response or TokenResponse()
        self.calls: list[dict[str, object]] = []

    def post(
        self,
        url: str,
        data: dict[str, str],
        timeout: int,
    ) -> FakeResponse:
        self.calls.append({"url": url, "data": data, "timeout": timeout})
        return self.response


def test_token_manager_uses_password_grant_with_user_credentials_only() -> None:
    session = _FakeSession()
    auth = GLPITokenManager(
        token_url="https://glpi.example.test/api.php/token",
        username="api-user",
        password="api-password",
        session=cast(requests.Session, session),
    )

    auth._acquire_token()

    assert session.calls[0]["data"] == {
        "grant_type": "password",
        "username": "api-user",
        "password": "api-password",
        "scope": "api",
    }
    assert auth.access_token == "token"


def test_token_manager_uses_client_credentials_grant() -> None:
    session = _FakeSession(response=TokenResponse(status_code=201))
    auth = GLPITokenManager(
        token_url="https://glpi.example.test/api.php/token",
        client_id="client-id",
        client_secret="client-secret",
        session=cast(requests.Session, session),
    )

    auth._acquire_token()

    assert session.calls[0]["data"] == {
        "grant_type": "client_credentials",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "scope": "api",
    }
    assert auth.access_token == "token"


def test_token_manager_preserves_raw_credential_text() -> None:
    session = _FakeSession(response=TokenResponse(status_code=201))
    auth = GLPITokenManager(
        token_url="https://glpi.example.test/api.php/token",
        client_id="  client-id  ",
        client_secret="  client-secret  ",
        session=cast(requests.Session, session),
    )

    auth._acquire_token()

    assert session.calls[0]["data"] == {
        "grant_type": "client_credentials",
        "client_id": "  client-id  ",
        "client_secret": "  client-secret  ",
        "scope": "api",
    }


def test_token_manager_uses_password_grant_with_both_credential_sets() -> None:
    session = _FakeSession()
    auth = GLPITokenManager(
        token_url="https://glpi.example.test/api.php/token",
        client_id="client-id",
        client_secret="client-secret",
        username="api-user",
        password="api-password",
        session=cast(requests.Session, session),
    )

    auth._acquire_token()

    assert session.calls[0]["data"] == {
        "grant_type": "password",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "username": "api-user",
        "password": "api-password",
        "scope": "api",
    }


def test_token_manager_refreshes_when_configured_interval_elapses() -> None:
    session = _FakeSession()
    auth = GLPITokenManager(
        token_url="https://glpi.example.test/api.php/token",
        client_id="client-id",
        client_secret="client-secret",
        session=cast(requests.Session, session),
        auth_token_refresh=60,
    )
    auth.access_token = "old-token"
    auth.refresh_token = "refresh-token"
    auth.token_updated_at = datetime.now(tz=timezone.utc) - timedelta(seconds=61)
    auth.token_expires_at = datetime.now(tz=timezone.utc) + timedelta(hours=1)

    auth.ensure_token()

    assert auth.auth_token_refresh == 60
    assert session.calls[0]["data"] == {
        "grant_type": "refresh_token",
        "refresh_token": "refresh-token",
        "client_id": "client-id",
        "client_secret": "client-secret",
    }
    assert auth.access_token == "token"


@pytest.mark.parametrize("refresh_interval", [0, -1])
def test_token_manager_rejects_non_positive_refresh_interval(
    refresh_interval: int,
) -> None:
    with pytest.raises(ValueError, match="auth_token_refresh"):
        GLPITokenManager(
            token_url="https://glpi.example.test/api.php/token",
            client_id="client-id",
            client_secret="client-secret",
            auth_token_refresh=refresh_interval,
        )


def test_token_manager_logout_clears_cached_tokens() -> None:
    auth = GLPITokenManager(
        token_url="https://glpi.example.test/api.php/token",
        client_id="client-id",
        client_secret="client-secret",
    )
    auth.access_token = "access-token"
    auth.refresh_token = "refresh-token"
    auth.token_updated_at = datetime.now(tz=timezone.utc)
    auth.token_expires_at = auth.token_updated_at + timedelta(hours=1)

    auth.logout()

    assert cast(str | None, auth.access_token) is None
    assert cast(str | None, auth.refresh_token) is None
    assert cast(datetime | None, auth.token_updated_at) is None
    assert cast(datetime | None, auth.token_expires_at) is None


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({}, "either client_id/client_secret, username/password, or both"),
        ({"client_id": "client-id"}, "both client_id and client_secret"),
        ({"client_secret": "client-secret"}, "both client_id and client_secret"),
        ({"username": "api-user"}, "both username and password"),
        ({"password": "api-password"}, "both username and password"),
    ],
)
def test_token_manager_rejects_incomplete_credentials(
    kwargs: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        GLPITokenManager(
            token_url="https://glpi.example.test/api.php/token",
            client_id=kwargs.get("client_id"),
            client_secret=kwargs.get("client_secret"),
            username=kwargs.get("username"),
            password=kwargs.get("password"),
        )


def test_oauth_401_raises_glpi_auth_error() -> None:
    """A rejected credential surfaces as ``GlpiAuthError``, not a bare ValueError."""

    session = _FakeSession(
        response=TokenResponse(status_code=401, payload={"error": "invalid_client"})
    )
    manager = GLPITokenManager(
        token_url="https://glpi.example.test/api.php/token",
        client_id="client-id",
        client_secret="wrong",
        session=cast(requests.Session, session),
    )
    with pytest.raises(GlpiAuthError) as excinfo:
        manager.ensure_token()

    assert excinfo.value.status_code == 401
    assert isinstance(excinfo.value, ValueError)


def test_oauth_401_is_not_retried() -> None:
    """A 4xx from the token endpoint is final; retrying cannot help."""

    session = _FakeSession(
        response=TokenResponse(status_code=401, payload={"error": "invalid_client"})
    )
    manager = GLPITokenManager(
        token_url="https://glpi.example.test/api.php/token",
        client_id="client-id",
        client_secret="wrong",
        session=cast(requests.Session, session),
    )
    with pytest.raises(GlpiAuthError):
        manager.ensure_token()

    assert len(session.calls) == 1


def test_oauth_5xx_raises_glpi_server_error_after_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 5xx from the token endpoint is retried, then reraised as-is."""

    monkeypatch.setattr(GLPITokenManager._acquire_token.retry, "wait", wait_fixed(0))
    session = _FakeSession(response=TokenResponse(status_code=503, payload={}))
    manager = GLPITokenManager(
        token_url="https://glpi.example.test/api.php/token",
        client_id="client-id",
        client_secret="client-secret",
        session=cast(requests.Session, session),
    )
    with pytest.raises(GlpiServerError) as excinfo:
        manager.ensure_token()

    assert excinfo.value.status_code == 503
    assert len(session.calls) == 3


def _make_refresh_ready_manager(
    session: _FakeSession,
) -> GLPITokenManager:
    """Return a manager primed so ``ensure_token`` reaches ``_refresh_access_token``.

    ``ensure_token`` only calls ``_refresh_access_token`` when an access
    token is already set *and* it is expired (or the proactive interval
    elapsed). ``_acquire_token`` is never reached this way, unlike a fresh
    manager, whose ``ensure_token`` always takes the acquire path.
    """

    manager = GLPITokenManager(
        token_url="https://glpi.example.test/api.php/token",
        client_id="client-id",
        client_secret="client-secret",
        session=cast(requests.Session, session),
    )
    manager.access_token = "stale-token"
    manager.refresh_token = "refresh-token"
    manager.token_updated_at = datetime.now(tz=timezone.utc) - timedelta(hours=2)
    manager.token_expires_at = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
    return manager


def test_refresh_401_stays_final_with_one_nested_acquire_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 4xx during refresh is not retried by either decorator.

    ``_refresh_access_token`` does not raise directly on a non-2xx response:
    it logs a warning and falls through to a *nested* ``_acquire_token()``
    call (auth.py:302-303), which carries its own, independent retry
    decorator. So even a "not retried" 4xx costs two POSTs -- one for the
    failed refresh, one for the nested acquire that raises
    ``GlpiAuthError`` -- rather than exactly one. Neither decorator's
    predicate matches ``GlpiAuthError``, so the count stops there instead
    of multiplying further (contrast with the 5xx case below).
    """

    monkeypatch.setattr(GLPITokenManager._acquire_token.retry, "wait", wait_fixed(0))
    monkeypatch.setattr(
        GLPITokenManager._refresh_access_token.retry, "wait", wait_fixed(0)
    )
    session = _FakeSession(
        response=TokenResponse(status_code=401, payload={"error": "invalid_grant"})
    )
    manager = _make_refresh_ready_manager(session)

    with pytest.raises(GlpiAuthError) as excinfo:
        manager.ensure_token()

    assert excinfo.value.status_code == 401
    # 1 refresh POST (logged, falls through) + 1 nested _acquire_token POST
    # (raises GlpiAuthError immediately; not retried by either decorator).
    assert len(session.calls) == 2


def test_refresh_5xx_persistent_multiplies_past_three_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A persistent 5xx during refresh costs 12 POSTs, not 3.

    KNOWN DEFECT, measured and pinned here (pre-existing, not introduced by
    the 4xx-fail-fast change in this task): ``_refresh_access_token`` falls
    through to a *nested* ``_acquire_token()`` call on any non-2xx response
    instead of raising directly (auth.py:302-303). Both methods are
    independently decorated with ``stop_after_attempt(3)``, and
    ``GlpiServerError`` is retryable by *both* decorators. A persistent 5xx
    therefore costs 3 (this method's attempts) x (1 refresh POST + 3 nested
    acquire POSTs) = 12 POST calls -- and ~24s of ``wait_fixed(3)`` sleep in
    production -- not the 3 attempts / ~6s the retry configuration alone
    would suggest.

    This test pins the measured reality so a future change (e.g. plan 3's
    httpx swap) cannot silently alter it. Restructuring the nested-retry
    topology itself is a deliberate design change and is out of scope here;
    see the plan-1 task-3 report for the full write-up.
    """

    monkeypatch.setattr(GLPITokenManager._acquire_token.retry, "wait", wait_fixed(0))
    monkeypatch.setattr(
        GLPITokenManager._refresh_access_token.retry, "wait", wait_fixed(0)
    )
    session = _FakeSession(response=TokenResponse(status_code=503, payload={}))
    manager = _make_refresh_ready_manager(session)

    with pytest.raises(GlpiServerError) as excinfo:
        manager.ensure_token()

    assert excinfo.value.status_code == 503
    assert len(session.calls) == 12


def test_acquire_token_network_error_is_retried_three_times(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A connection-level failure (no HTTP response at all) is retried.

    Mirrors ``test_network_errors_are_still_retried`` in
    ``clients/commons/tests/test_retry_semantics.py`` for the transport, but
    covers the OAuth token path, which previously had no equivalent test.
    """

    monkeypatch.setattr(GLPITokenManager._acquire_token.retry, "wait", wait_fixed(0))

    class _FailingSession:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def post(self, url: str, data: dict[str, str], timeout: int) -> FakeResponse:
            self.calls.append({"url": url, "data": data, "timeout": timeout})
            raise requests.ConnectionError("network down")

    session = _FailingSession()
    manager = GLPITokenManager(
        token_url="https://glpi.example.test/api.php/token",
        client_id="client-id",
        client_secret="client-secret",
        session=cast(requests.Session, session),
    )

    with pytest.raises(requests.ConnectionError):
        manager.ensure_token()

    assert len(session.calls) == 3
