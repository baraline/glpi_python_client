from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import pytest

from glpi_python_client import GlpiClient, GlpiDocument, GlpiLocation, GlpiUser
from glpi_python_client.testing.utils import FakeResponse

_V1_BASE_URLS = (
    pytest.param("https://glpi.example.test/api.php/v1", id="api.php-v1"),
    pytest.param("https://glpi.example.test/apirest.php", id="apirest.php"),
)


def _empty_response() -> FakeResponse:
    return FakeResponse(status_code=204, payload={}, text="", content=b"")


def test_client_rejects_legacy_base_url_keyword() -> None:
    with pytest.raises(TypeError, match="base_url"):
        GlpiClient(
            base_url="https://glpi.example.test/api.php",  # type: ignore[call-arg]
            client_id="client-id",
            client_secret="client-secret",
        )


def test_client_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLPI_API_URL", "https://glpi.example.test/api.php")
    monkeypatch.setenv("GLPI_CLIENT_ID", "client-id")
    monkeypatch.setenv("GLPI_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GLPI_USERNAME", "api-user")
    monkeypatch.setenv("GLPI_PASSWORD", "api-password")
    monkeypatch.setenv("GLPI_ENTITY", "4")
    monkeypatch.setenv("GLPI_PROFILE", "5")
    monkeypatch.setenv("GLPI_ENTITY_RECURSIVE", "yes")
    monkeypatch.setenv("GLPI_VERIFY_SSL", "false")
    monkeypatch.setenv("GLPI_AUTH_TOKEN_REFRESH", "120")

    client = GlpiClient.from_env()
    try:
        assert client.glpi_api_url == "https://glpi.example.test/api.php"
        assert client.glpi_entity == 4
        assert client.glpi_profile == 5
        assert client.entity_recursive is True
        assert client._session.verify is False
        assert client._auth.auth_token_refresh == 120
    finally:
        client.close()


def test_client_from_env_none_overrides_clear_optional_env_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GLPI_API_URL", "https://glpi.example.test/api.php")
    monkeypatch.setenv("GLPI_CLIENT_ID", "client-id")
    monkeypatch.setenv("GLPI_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GLPI_AUTH_TOKEN_REFRESH", "120")
    monkeypatch.setenv("GLPI_V1_BASE_URL", "https://glpi.example.test/apirest.php")
    monkeypatch.setenv("GLPI_V1_USER_TOKEN", "user-token")

    client = GlpiClient.from_env(
        auth_token_refresh=None,
        v1_base_url=None,
        v1_user_token=None,
    )
    try:
        assert client._auth.auth_token_refresh is None
        assert client._v1 is None
    finally:
        client.close()


def test_client_from_env_rejects_invalid_integer_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GLPI_API_URL", "https://glpi.example.test/api.php")
    monkeypatch.setenv("GLPI_CLIENT_ID", "client-id")
    monkeypatch.setenv("GLPI_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GLPI_ENTITY", "abc")

    with pytest.raises(ValueError):
        GlpiClient.from_env()


def test_client_from_env_rejects_invalid_boolean_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GLPI_API_URL", "https://glpi.example.test/api.php")
    monkeypatch.setenv("GLPI_CLIENT_ID", "client-id")
    monkeypatch.setenv("GLPI_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GLPI_VERIFY_SSL", " definitely ")

    with pytest.raises(ValueError, match="Invalid boolean"):
        GlpiClient.from_env()


def test_client_context_manager_logs_out_and_rejects_future_calls(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()
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

    with client as managed_client:
        assert managed_client is client

    assert events == ["logout", "session_close"]
    assert cast(str | None, client._auth.access_token) is None
    with pytest.raises(RuntimeError, match="closed"):
        client.get_ticket_record("123")


def test_client_from_env_requires_glpi_api_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLPI_BASE_URL", "https://glpi.example.test/api.php")
    monkeypatch.setenv("GLPI_CLIENT_ID", "client-id")
    monkeypatch.setenv("GLPI_CLIENT_SECRET", "client-secret")

    with pytest.raises(ValueError, match="glpi_api_url"):
        GlpiClient.from_env()


@pytest.mark.parametrize("v1_base_url", _V1_BASE_URLS)
def test_client_preserves_explicit_v1_base_url(v1_base_url: str) -> None:
    client = GlpiClient(
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
        client.close()


@pytest.mark.parametrize(
    "v1_kwargs",
    [
        {"v1_base_url": "https://glpi.example.test/apirest.php"},
        {"v1_user_token": "user-token"},
    ],
)
def test_client_rejects_partial_v1_document_config(
    v1_kwargs: dict[str, Any],
) -> None:
    with pytest.raises(ValueError, match=r"v1_base_url.*v1_user_token"):
        GlpiClient(
            glpi_api_url="https://glpi.example.test/api.php",
            client_id="client-id",
            client_secret="client-secret",
            **v1_kwargs,
        )


@pytest.mark.parametrize(
    "env_values",
    [
        {
            "GLPI_USERNAME": "api-user",
            "GLPI_PASSWORD": "api-password",
        },
        {
            "GLPI_CLIENT_ID": "client-id",
            "GLPI_CLIENT_SECRET": "client-secret",
        },
    ],
)
def test_client_from_env_accepts_each_supported_auth_pair(
    monkeypatch: pytest.MonkeyPatch,
    env_values: dict[str, str],
) -> None:
    monkeypatch.setenv("GLPI_API_URL", "https://glpi.example.test/api.php")
    for key, value in env_values.items():
        monkeypatch.setenv(key, value)

    client = GlpiClient.from_env()
    try:
        assert client.glpi_api_url == "https://glpi.example.test/api.php"
    finally:
        client.close()


def test_create_user_uses_sync_transport(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()
    requests: list[dict[str, object]] = []

    def ensure_token() -> None:
        client._auth.access_token = "token"

    def post(url: str, **kwargs: object) -> FakeResponse:
        requests.append({"url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr(client._auth, "ensure_token", ensure_token)
    monkeypatch.setattr(client._session, "post", post)
    try:
        created = client.create_user(GlpiUser(email="ada@example.test"))

        assert created == "321"
        assert requests[0]["url"] == (
            "https://glpi.example.test/api.php/Administration/User"
        )
        assert cast(dict[str, object], requests[0]["json"])["email"] == (
            "ada@example.test"
        )
    finally:
        client.close()


def test_delete_user_returns_none(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()

    def fake_delete_request(
        endpoint: str,
        payload: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> FakeResponse:
        assert endpoint == "Administration/User/42"
        assert payload is None
        assert skip_entity is False
        return _empty_response()

    monkeypatch.setattr(client, "_delete_request", fake_delete_request)
    try:
        client.delete_user(42)
    finally:
        client.close()


def test_create_location_requires_name(
    client_factory: Callable[..., GlpiClient],
) -> None:
    client = client_factory()
    try:
        with pytest.raises(ValueError, match="location creation requires a name"):
            client.create_location(GlpiLocation(entity_id=7))
    finally:
        client.close()


def test_delete_location_returns_none(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()

    def fake_delete_request(
        endpoint: str,
        payload: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> FakeResponse:
        assert endpoint == "Dropdowns/Location/9"
        assert payload is None
        assert skip_entity is False
        return _empty_response()

    monkeypatch.setattr(client, "_delete_request", fake_delete_request)
    try:
        client.delete_location(9)
    finally:
        client.close()


def test_upload_document_to_ticket_uses_v1_upload_session(
    client_factory: Callable[..., GlpiClient],
) -> None:
    client = client_factory(glpi_entity=7)
    upload_calls: list[dict[str, object]] = []

    class FakeV1Session:
        def close(self) -> None:
            return None

        def upload_document(
            self,
            filename: str,
            content: bytes,
            mime_type: str,
            *,
            document_name: str,
            ticket_id: int,
            entity_id: int | None,
        ) -> dict[str, object]:
            upload_calls.append(
                {
                    "filename": filename,
                    "content": content,
                    "mime_type": mime_type,
                    "document_name": document_name,
                    "ticket_id": ticket_id,
                    "entity_id": entity_id,
                }
            )
            return {"id": "654"}

    client._v1 = cast(Any, FakeV1Session())
    try:
        uploaded = client.upload_document_to_ticket(
            GlpiDocument(
                ticket_id=123,
                filename="trace.txt",
                content=b"trace",
                mime_type="text/plain",
            )
        )

        assert upload_calls == [
            {
                "filename": "trace.txt",
                "content": b"trace",
                "mime_type": "text/plain",
                "document_name": "Document ticket 123",
                "ticket_id": 123,
                "entity_id": 7,
            }
        ]
        assert uploaded.ticket_id == 123
        assert uploaded.document_id == "654"
        assert uploaded.document_name == "Document ticket 123"
        assert uploaded.filename == "trace.txt"
    finally:
        client.close()
