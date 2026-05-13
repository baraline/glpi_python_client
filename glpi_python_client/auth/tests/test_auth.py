from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import cast

import pytest
import requests

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
