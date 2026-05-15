"""Unit tests for client setup, configuration, and lifecycle helpers."""

from __future__ import annotations

import os
from typing import Any

import pytest

from glpi_python_client import GlpiClient
from glpi_python_client.clients.commons._config import (
    build_client_env_config,
    normalize_client_api_url,
    parse_optional_env_bool,
    parse_optional_env_int,
    validate_v1_document_config,
)


def test_normalize_client_api_url_strips_trailing_slash() -> None:
    """The helper trims one trailing slash for consistent endpoint joins."""

    assert (
        normalize_client_api_url("https://glpi.test/api.php/v2/", client_name="X")
        == "https://glpi.test/api.php/v2"
    )


def test_normalize_client_api_url_rejects_missing_value() -> None:
    """Missing or empty URL raises ``ValueError`` with the client name."""

    with pytest.raises(ValueError, match="X requires glpi_api_url"):
        normalize_client_api_url(None, client_name="X")
    with pytest.raises(ValueError, match="X requires glpi_api_url"):
        normalize_client_api_url("", client_name="X")
    with pytest.raises(ValueError, match="X requires glpi_api_url"):
        normalize_client_api_url(123, client_name="X")  # type: ignore[arg-type]


def test_validate_v1_document_config_rejects_partial_pair() -> None:
    """Either both v1 values are present or both are absent."""

    with pytest.raises(ValueError, match="v1_base_url and v1_user_token"):
        validate_v1_document_config(v1_base_url="https://x", v1_user_token=None)
    with pytest.raises(ValueError, match="v1_base_url and v1_user_token"):
        validate_v1_document_config(v1_base_url=None, v1_user_token="t")


def test_validate_v1_document_config_allows_complete_pair() -> None:
    """A complete v1 pair (or no v1 at all) does not raise."""

    validate_v1_document_config(v1_base_url=None, v1_user_token=None)
    validate_v1_document_config(v1_base_url="https://x", v1_user_token="t")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (5, 5),
        ("7", 7),
    ],
)
def test_parse_optional_env_int(value: object, expected: int | None) -> None:
    """Environment integer parsing accepts None, int, and numeric strings."""

    assert parse_optional_env_int(value) == expected


def test_parse_optional_env_int_rejects_other_types() -> None:
    """Non-string non-int inputs raise ``TypeError``."""

    with pytest.raises(TypeError):
        parse_optional_env_int(1.5)


@pytest.mark.parametrize(
    ("value", "default", "expected"),
    [
        (None, True, True),
        (None, False, False),
        (True, False, True),
        ("1", False, True),
        ("yes", False, True),
        ("ON", False, True),
        ("0", True, False),
        ("false", True, False),
        ("OFF", True, False),
    ],
)
def test_parse_optional_env_bool_truthy_and_falsy(
    value: object, default: bool, expected: bool
) -> None:
    """Boolean parsing handles strings, native booleans, and the default."""

    assert parse_optional_env_bool(value, default=default) is expected


def test_parse_optional_env_bool_rejects_unknown_string() -> None:
    """Unknown strings raise ``ValueError``."""

    with pytest.raises(ValueError):
        parse_optional_env_bool("maybe", default=False)


def test_parse_optional_env_bool_rejects_other_types() -> None:
    """Non-string non-bool inputs raise ``TypeError``."""

    with pytest.raises(TypeError):
        parse_optional_env_bool(1, default=False)


def test_build_client_env_config_overrides_win() -> None:
    """Explicit overrides win over environment values."""

    env = {"GLPI_API_URL": "https://env", "GLPI_VERIFY_SSL": "false"}
    config = build_client_env_config(
        prefix="GLPI_",
        env=env,
        overrides={"glpi_api_url": "https://override"},
    )
    assert config["glpi_api_url"] == "https://override"
    assert config["verify_ssl"] is False
    assert config["language"] == "en_GB"


async def test_glpi_client_from_env_uses_overrides_and_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``GlpiClient.from_env`` resolves env vars and applies overrides."""

    env = {
        "GLPI_API_URL": "https://glpi.example.test/api.php/v2",
        "GLPI_USERNAME": "u",
        "GLPI_PASSWORD": "p",
    }
    client = GlpiClient.from_env(env=env)
    try:
        assert client.glpi_api_url.endswith("/api.php/v2")
    finally:
        await client.close()


async def test_glpi_client_close_is_idempotent() -> None:
    """Calling ``close`` twice does not raise."""

    client = GlpiClient(
        glpi_api_url="https://glpi.example.test/api.php/v2",
        username="u",
        password="p",
    )
    await client.close()
    await client.close()


async def test_glpi_client_async_context_manager() -> None:
    """Using ``async with`` closes the client on exit."""

    async with GlpiClient(
        glpi_api_url="https://glpi.example.test/api.php/v2",
        username="u",
        password="p",
    ) as client:
        assert client.glpi_api_url.endswith("/api.php/v2")
    # After __aexit__ the client is closed and rejects further calls.
    with pytest.raises(RuntimeError, match="closed"):
        await client._ensure_token()


def test_glpi_client_rejects_invalid_credentials() -> None:
    """Constructor refuses to build a client with no usable credentials."""

    with pytest.raises(ValueError):
        GlpiClient(glpi_api_url="https://glpi.example.test/api.php/v2")


async def test_glpi_client_v1_session_built_when_configured() -> None:
    """Providing v1_base_url + v1_user_token instantiates the v1 session."""

    client = GlpiClient(
        glpi_api_url="https://glpi.example.test/api.php/v2",
        username="u",
        password="p",
        v1_base_url="https://glpi.example.test/apirest.php",
        v1_user_token="user-token",
        v1_app_token="app-token",
    )
    try:
        assert client._v1 is not None
    finally:
        await client.close()


def test_glpi_client_rejects_partial_v1_config() -> None:
    """Half-configured v1 values raise at construction time."""

    with pytest.raises(ValueError, match="v1_base_url and v1_user_token"):
        GlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/v2",
            username="u",
            password="p",
            v1_base_url="https://glpi.example.test/apirest.php",
        )


async def test_environ_default_is_used_when_env_argument_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no env mapping is provided ``os.environ`` is used."""

    monkeypatch.setenv("GLPI_API_URL", "https://from-environ.example/api.php/v2")
    monkeypatch.setenv("GLPI_USERNAME", "u")
    monkeypatch.setenv("GLPI_PASSWORD", "p")
    client = GlpiClient.from_env()
    try:
        assert client.glpi_api_url.endswith("/api.php/v2")
    finally:
        await client.close()


async def test_async_transport_ensure_open_blocks_after_close() -> None:
    """Closed clients raise on subsequent transport calls."""

    client = GlpiClient(
        glpi_api_url="https://glpi.example.test/api.php/v2",
        username="u",
        password="p",
    )
    await client.close()
    with pytest.raises(RuntimeError, match="closed"):
        client._ensure_open()


def test_glpi_client_init_failure_closes_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing token-manager init releases the underlying session."""

    closed: dict[str, Any] = {}

    import requests

    original_close = requests.Session.close

    def _track_close(self: requests.Session) -> None:
        closed["closed"] = True
        original_close(self)

    monkeypatch.setattr(requests.Session, "close", _track_close)
    with pytest.raises(ValueError):
        GlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/v2",
            client_id="only-id-no-secret",
        )
    assert closed.get("closed") is True


def test_no_other_vars_leak_into_environ_test() -> None:
    """Sanity check that environment unset values stay None."""

    config = build_client_env_config(
        prefix="GLPI_",
        env={k: v for k, v in os.environ.items() if not k.startswith("GLPI_")},
        overrides={},
    )
    assert config["glpi_api_url"] is None
