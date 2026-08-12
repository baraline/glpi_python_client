"""Unit tests for client construction and lifecycle helpers."""

from __future__ import annotations

import os
from typing import Any

import pytest

from glpi_python_client import GlpiClient
from glpi_python_client._sync._testing import make_client
from glpi_python_client._sync.clients.commons._config import build_client_env_config


def test_glpi_client_from_env_uses_overrides_and_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``from_env`` resolves env vars and applies overrides."""

    env = {
        "GLPI_API_URL": "https://glpi.example.test/api.php/v2",
        "GLPI_USERNAME": "u",
        "GLPI_PASSWORD": "p",
        "GLPI_SERVER_TIMEZONE": "Europe/Paris",
    }
    client = GlpiClient.from_env(env=env)
    try:
        assert client.glpi_api_url.endswith("/api.php/v2")
    finally:
        client.close()


def test_glpi_client_close_is_idempotent() -> None:
    """Calling ``close`` twice does not raise."""

    client = GlpiClient(
        glpi_api_url="https://glpi.example.test/api.php/v2",
        server_timezone="Europe/Paris",
        username="u",
        password="p",
    )
    client.close()
    client.close()


def test_glpi_client_async_context_manager() -> None:
    """The context manager closes the client on exit."""

    with make_client() as c:
        assert c._session is not None
    assert c._closed is True
    # Closing must be observable, not just recorded on a private flag:
    # every transport helper goes through _ensure_open, so the first one
    # reached after the block has to refuse. Match the guard's own message,
    # not the bare word "closed" -- with the guard disabled the call still
    # raises RuntimeError, but from httpx ("Cannot send a request, as the
    # client has been closed."), so the looser pattern passes either way.
    with pytest.raises(RuntimeError, match="GLPI client is closed"):
        c._ensure_token()


def test_glpi_client_rejects_invalid_credentials() -> None:
    """Constructor refuses to build a client with no usable credentials."""

    with pytest.raises(ValueError):
        GlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/v2",
            server_timezone="Europe/Paris",
        )


def test_glpi_client_v1_session_built_when_configured() -> None:
    """Providing v1_base_url + v1_user_token instantiates the v1 session."""

    client = GlpiClient(
        glpi_api_url="https://glpi.example.test/api.php/v2",
        server_timezone="Europe/Paris",
        username="u",
        password="p",
        v1_base_url="https://glpi.example.test/apirest.php",
        v1_user_token="user-token",
        v1_app_token="app-token",
    )
    try:
        assert client._v1 is not None
    finally:
        client.close()


def test_glpi_client_rejects_partial_v1_config() -> None:
    """Half-configured v1 values raise at construction time."""

    with pytest.raises(ValueError, match="v1_base_url and v1_user_token"):
        GlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/v2",
            server_timezone="Europe/Paris",
            username="u",
            password="p",
            v1_base_url="https://glpi.example.test/apirest.php",
        )


def test_environ_default_is_used_when_env_argument_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no env mapping is provided ``os.environ`` is used."""

    monkeypatch.setenv("GLPI_API_URL", "https://from-environ.example/api.php/v2")
    monkeypatch.setenv("GLPI_USERNAME", "u")
    monkeypatch.setenv("GLPI_PASSWORD", "p")
    monkeypatch.setenv("GLPI_SERVER_TIMEZONE", "Europe/Paris")
    client = GlpiClient.from_env()
    try:
        assert client.glpi_api_url.endswith("/api.php/v2")
    finally:
        client.close()


def test_async_transport_ensure_open_blocks_after_close() -> None:
    """Closed clients raise on subsequent transport calls."""

    client = GlpiClient(
        glpi_api_url="https://glpi.example.test/api.php/v2",
        server_timezone="Europe/Paris",
        username="u",
        password="p",
    )
    client.close()
    with pytest.raises(RuntimeError, match="closed"):
        client._ensure_open()


def test_glpi_client_init_failure_creates_no_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bad credential set is rejected before any session is constructed.

    This used to build the session first and unwind it from an ``except``
    clause. That assumes a constructor can always close a partially built
    session before it returns, which is not something every client variant
    guarantees -- so the configuration is now validated up front instead.

    Asserting *nothing was built* is the stronger property: there is no
    window in which a session exists but the client does not, so there is
    nothing that can leak if the unwind is ever missed.
    """

    import httpx

    constructed: list[object] = []
    original_init = httpx.Client.__init__

    def _track_init(self: httpx.Client, *args: Any, **kwargs: Any) -> None:
        constructed.append(self)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", _track_init)
    with pytest.raises(ValueError):
        GlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/v2",
            server_timezone="Europe/Paris",
            client_id="only-id-no-secret",
        )
    assert constructed == [], "a transport session was built for a rejected config"


def test_no_other_vars_leak_into_environ_test() -> None:
    """Sanity check that environment unset values stay None."""

    config = build_client_env_config(
        prefix="GLPI_",
        env={k: v for k, v in os.environ.items() if not k.startswith("GLPI_")},
        overrides={},
    )
    assert config["glpi_api_url"] is None
