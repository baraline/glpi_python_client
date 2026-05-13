from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest

from glpi_python_client import AsyncGlpiClient, GlpiUser
from glpi_python_client.testing.utils import FakeResponse

_V1_BASE_URLS = (
    pytest.param("https://glpi.example.test/api.php/v1", id="api.php-v1"),
    pytest.param("https://glpi.example.test/apirest.php", id="apirest.php"),
)


def _empty_response() -> FakeResponse:
    return FakeResponse(status_code=204, payload={}, text="", content=b"")


def test_async_client_rejects_legacy_base_url_keyword() -> None:
    with pytest.raises(TypeError, match="base_url"):
        AsyncGlpiClient(
            base_url="https://glpi.example.test/api.php",  # type: ignore[call-arg]
            client_id="client-id",
            client_secret="client-secret",
        )


def test_async_client_rejects_constructor_batch_size_keyword() -> None:
    with pytest.raises(TypeError, match="batch_size"):
        AsyncGlpiClient(
            glpi_api_url="https://glpi.example.test/api.php",
            client_id="client-id",
            client_secret="client-secret",
            batch_size=100,  # type: ignore[call-arg]
        )


def test_async_client_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLPI_API_URL", "https://glpi.example.test/api.php")
    monkeypatch.setenv("GLPI_CLIENT_ID", "client-id")
    monkeypatch.setenv("GLPI_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GLPI_AUTH_TOKEN_REFRESH", "90")

    client = AsyncGlpiClient.from_env()
    try:
        assert client.glpi_api_url == "https://glpi.example.test/api.php"
        assert client._auth.auth_token_refresh == 90
    finally:
        asyncio.run(client.close())


def test_async_client_from_env_none_overrides_clear_optional_env_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GLPI_API_URL", "https://glpi.example.test/api.php")
    monkeypatch.setenv("GLPI_CLIENT_ID", "client-id")
    monkeypatch.setenv("GLPI_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GLPI_AUTH_TOKEN_REFRESH", "90")
    monkeypatch.setenv("GLPI_V1_BASE_URL", "https://glpi.example.test/apirest.php")
    monkeypatch.setenv("GLPI_V1_USER_TOKEN", "user-token")

    client = AsyncGlpiClient.from_env(
        auth_token_refresh=None,
        v1_base_url=None,
        v1_user_token=None,
    )
    try:
        assert client._auth.auth_token_refresh is None
        assert client._v1 is None
    finally:
        asyncio.run(client.close())


def test_async_client_from_env_rejects_invalid_integer_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GLPI_API_URL", "https://glpi.example.test/api.php")
    monkeypatch.setenv("GLPI_CLIENT_ID", "client-id")
    monkeypatch.setenv("GLPI_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GLPI_AUTH_TOKEN_REFRESH", "abc")

    with pytest.raises(ValueError):
        AsyncGlpiClient.from_env()


def test_async_client_from_env_rejects_invalid_boolean_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GLPI_API_URL", "https://glpi.example.test/api.php")
    monkeypatch.setenv("GLPI_CLIENT_ID", "client-id")
    monkeypatch.setenv("GLPI_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GLPI_ENTITY_RECURSIVE", " definitely ")

    with pytest.raises(ValueError, match="Invalid boolean"):
        AsyncGlpiClient.from_env()


def test_async_client_context_manager_logs_out_and_rejects_future_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_test() -> None:
        client = AsyncGlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/",
            client_id="client-id",
            client_secret="client-secret",
        )
        events: list[str] = []
        original_logout = client._auth.logout
        original_session_close = client._session.close

        def logout() -> None:
            events.append("logout")
            original_logout()

        def close_session() -> None:
            events.append("session_close")
            original_session_close()

        monkeypatch.setattr(client._auth, "logout", logout)
        monkeypatch.setattr(client._session, "close", close_session)

        client._auth.access_token = "access-token"

        async with client as managed_client:
            assert managed_client is client

        assert events == ["logout", "session_close"]
        assert cast(str | None, client._auth.access_token) is None
        with pytest.raises(RuntimeError, match="closed"):
            await client.get_ticket_record("123")

    asyncio.run(run_test())


def test_async_client_from_env_requires_glpi_api_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GLPI_BASE_URL", "https://glpi.example.test/api.php")
    monkeypatch.setenv("GLPI_CLIENT_ID", "client-id")
    monkeypatch.setenv("GLPI_CLIENT_SECRET", "client-secret")

    with pytest.raises(ValueError, match="glpi_api_url"):
        AsyncGlpiClient.from_env()


@pytest.mark.parametrize("v1_base_url", _V1_BASE_URLS)
def test_async_client_preserves_explicit_v1_base_url(v1_base_url: str) -> None:
    client = AsyncGlpiClient(
        glpi_api_url="https://glpi.example.test/api.php",
        client_id="client-id",
        client_secret="client-secret",
        v1_base_url=v1_base_url,
        v1_user_token="user-token",
    )

    try:
        assert client._v1 is not None
        assert client._v1._base_url == v1_base_url
    finally:
        asyncio.run(client.close())


@pytest.mark.parametrize(
    "v1_kwargs",
    [
        {"v1_base_url": "https://glpi.example.test/apirest.php"},
        {"v1_user_token": "user-token"},
    ],
)
def test_async_client_rejects_partial_v1_document_config(
    v1_kwargs: dict[str, Any],
) -> None:
    with pytest.raises(ValueError, match=r"v1_base_url.*v1_user_token"):
        AsyncGlpiClient(
            glpi_api_url="https://glpi.example.test/api.php",
            client_id="client-id",
            client_secret="client-secret",
            **v1_kwargs,
        )


def test_async_create_user_uses_async_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_test() -> None:
        client = AsyncGlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/",
            client_id="client-id",
            client_secret="client-secret",
        )
        requests: list[dict[str, object]] = []

        def ensure_token() -> None:
            client._auth.access_token = "token"

        def post(url: str, **kwargs: object) -> FakeResponse:
            requests.append({"url": url, **kwargs})
            return FakeResponse()

        monkeypatch.setattr(client._auth, "ensure_token", ensure_token)
        monkeypatch.setattr(client._session, "post", post)
        try:
            created = await client.create_user(GlpiUser(email="ada@example.test"))

            assert created == "321"
            assert requests[0]["url"] == (
                "https://glpi.example.test/api.php/Administration/User"
            )
            assert cast(dict[str, object], requests[0]["json"])["email"] == (
                "ada@example.test"
            )
        finally:
            await client.close()

    asyncio.run(run_test())


@pytest.mark.parametrize(
    ("method_name", "args", "expected_endpoint"),
    [
        ("delete_user", (42,), "Administration/User/42"),
        ("delete_location", (9,), "Dropdowns/Location/9"),
    ],
)
def test_async_provisioning_delete_operations_return_none(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    args: tuple[object, ...],
    expected_endpoint: str,
) -> None:
    async def run_test() -> None:
        client = AsyncGlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/",
            client_id="client-id",
            client_secret="client-secret",
        )

        async def fake_delete_request(
            endpoint: str,
            payload: dict[str, object] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            assert endpoint == expected_endpoint
            assert payload is None
            assert skip_entity is False
            return _empty_response()

        monkeypatch.setattr(client, "_delete_request", fake_delete_request)
        try:
            operation = getattr(client, method_name)
            await operation(*args)
        finally:
            await client.close()

    asyncio.run(run_test())
