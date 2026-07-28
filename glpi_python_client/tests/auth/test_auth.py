from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import cast

import httpx
import pytest
from tenacity import wait_fixed

from glpi_python_client import (
    GlpiAuthError,
    GlpiServerError,
    GlpiTransportError,
    GlpiValidationError,
)
from glpi_python_client._sync.auth.auth import GLPITokenManager
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
        session=cast(httpx.Client, session),
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
        session=cast(httpx.Client, session),
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
        session=cast(httpx.Client, session),
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
        session=cast(httpx.Client, session),
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
        session=cast(httpx.Client, session),
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
    """``GlpiValidationError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working.
    """

    with pytest.raises(GlpiValidationError, match="auth_token_refresh") as excinfo:
        GLPITokenManager(
            token_url="https://glpi.example.test/api.php/token",
            client_id="client-id",
            client_secret="client-secret",
            auth_token_refresh=refresh_interval,
        )
    assert isinstance(excinfo.value, ValueError)


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
    """``GlpiValidationError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working.
    """

    with pytest.raises(GlpiValidationError, match=message) as excinfo:
        GLPITokenManager(
            token_url="https://glpi.example.test/api.php/token",
            client_id=kwargs.get("client_id"),
            client_secret=kwargs.get("client_secret"),
            username=kwargs.get("username"),
            password=kwargs.get("password"),
        )
    assert isinstance(excinfo.value, ValueError)


def test_oauth_401_raises_glpi_auth_error() -> None:
    """A rejected credential surfaces as ``GlpiAuthError``, not a bare ValueError."""

    session = _FakeSession(
        response=TokenResponse(status_code=401, payload={"error": "invalid_client"})
    )
    manager = GLPITokenManager(
        token_url="https://glpi.example.test/api.php/token",
        client_id="client-id",
        client_secret="wrong",
        session=cast(httpx.Client, session),
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
        session=cast(httpx.Client, session),
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
        session=cast(httpx.Client, session),
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
        session=cast(httpx.Client, session),
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


def test_refresh_5xx_persistent_costs_one_refresh_plus_nested_acquire_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A persistent 5xx during refresh costs 4 POSTs, not 12.

    ``_refresh_access_token`` falls through to a *nested* ``_acquire_token()``
    call on any non-2xx response instead of raising directly
    (auth.py:327-332). That nested call is independently decorated with
    ``stop_after_attempt(3)`` and retries ``GlpiServerError``. This method's
    own decorator only matches ``httpx.HTTPError`` (a genuine
    network fault on the refresh POST itself), not ``GlpiServerError``, so it
    does not retry the fall-through a second time on top of the nested
    call's own retries.

    A persistent 5xx therefore costs exactly 1 refresh POST + 3 nested
    acquire POSTs = 4 POST calls -- not the 3 (this method's attempts) x 4
    = 12 that resulted from a previous predicate that also matched
    ``GlpiServerError`` here, duplicating the nested retries. This test pins
    the fixed count so a future change (e.g. plan 3's httpx swap) cannot
    silently reintroduce the multiplication.
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
    assert len(session.calls) == 4


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
            raise httpx.ConnectError("network down")

    session = _FailingSession()
    manager = GLPITokenManager(
        token_url="https://glpi.example.test/api.php/token",
        client_id="client-id",
        client_secret="client-secret",
        session=cast(httpx.Client, session),
    )

    with pytest.raises(GlpiTransportError):
        manager.ensure_token()

    assert len(session.calls) == 3


def test_refresh_network_error_is_retried_three_times(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A connection-level failure during refresh is retried by refresh's own decorator.

    Pins the one predicate member not yet covered by another test:
    ``_refresh_access_token``'s network-error retry. The fall-through
    ``GlpiServerError`` case is pinned by
    ``test_refresh_5xx_persistent_costs_one_refresh_plus_nested_acquire_attempts``
    above, and ``_acquire_token``'s network retry is pinned by
    ``test_acquire_token_network_error_is_retried_three_times``. A
    ``httpx.ConnectError`` raised by ``session.post`` is translated to
    ``GlpiTransportError`` and propagates
    *before* ``_refresh_access_token`` reaches its non-2xx fallthrough
    branch (auth.py:327-332), so the nested ``_acquire_token`` call is
    never reached here -- unlike the persistent-5xx case, this pins
    refresh's network retry count at 3, not 12. If a future rewrite of the
    retry predicate (e.g. the httpx transport swap) drops this to 1
    without remapping the equivalent network exception, this test catches
    it with every other test still green.
    """

    monkeypatch.setattr(
        GLPITokenManager._refresh_access_token.retry, "wait", wait_fixed(0)
    )

    class _FailingSession:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def post(self, url: str, data: dict[str, str], timeout: int) -> FakeResponse:
            self.calls.append({"url": url, "data": data, "timeout": timeout})
            raise httpx.ConnectError("network down")

    session = _FailingSession()
    manager = _make_refresh_ready_manager(cast(_FakeSession, session))

    with pytest.raises(GlpiTransportError):
        manager.ensure_token()

    assert len(session.calls) == 3
