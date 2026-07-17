"""Configuration and resource setup for the asynchronous GLPI client.

The helpers here own environment parsing, URL normalisation, SSL warning
behaviour, and the construction of the runtime resources used by
:class:`glpi_python_client.clients.sync_client.GlpiClient` and
:class:`glpi_python_client.clients.async_client.AsyncGlpiClient`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

import requests
import urllib3

from glpi_python_client._errors import GlpiValidationError

if TYPE_CHECKING:
    from glpi_python_client.auth._v1_session import GLPIV1Session
    from glpi_python_client.auth.auth import GLPITokenManager


@dataclass(frozen=True)
class ClientResources:
    """Runtime resources owned by one async ``GlpiClient`` instance.

    The bundle keeps shared HTTP session, token manager, and optional v1
    upload session tied together so the client can release them as a unit.
    """

    glpi_api_url: str
    session: requests.Session
    auth: GLPITokenManager
    v1: GLPIV1Session | None


def configure_ssl_warning_policy(*, verify_ssl: bool) -> None:
    """Adjust insecure-request warning behaviour for the configured SSL policy.

    When certificate verification is disabled, urllib3 warnings are muted so
    callers do not get repeated noise from every request made by the
    client.
    """

    if verify_ssl:
        return
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def build_client_resources(
    *,
    glpi_api_url: object,
    client_name: str,
    client_id: str | None,
    client_secret: str | None,
    username: str | None,
    password: str | None,
    verify_ssl: bool,
    auth_token_refresh: int | None,
    v1_base_url: str | None,
    v1_user_token: str | None,
    v1_app_token: str | None,
) -> ClientResources:
    """Build the shared resources required by one async client instance.

    The helper validates the API URL, configures SSL behaviour, builds the
    OAuth token manager, and optionally instantiates the legacy v1 session
    used solely by the document upload mixin.
    """

    from glpi_python_client.auth._v1_session import GLPIV1Session
    from glpi_python_client.auth.auth import GLPITokenManager

    normalized_api_url = normalize_client_api_url(
        glpi_api_url,
        client_name=client_name,
    )
    validate_v1_document_config(
        v1_base_url=v1_base_url,
        v1_user_token=v1_user_token,
    )
    configure_ssl_warning_policy(verify_ssl=verify_ssl)

    session = requests.Session()
    session.verify = verify_ssl
    try:
        auth = GLPITokenManager(
            token_url=f"{normalized_api_url}/token",
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            session=session,
            auth_token_refresh=auth_token_refresh,
        )
    except Exception:
        session.close()
        raise

    v1: GLPIV1Session | None = None
    if v1_base_url and v1_user_token:
        v1 = GLPIV1Session(
            base_url=v1_base_url,
            user_token=v1_user_token,
            app_token=v1_app_token,
            verify_ssl=verify_ssl,
        )

    return ClientResources(
        glpi_api_url=normalized_api_url,
        session=session,
        auth=auth,
        v1=v1,
    )


def parse_optional_env_int(value: object) -> int | None:
    """Parse one optional integer from an environment-style value.

    ``None`` is preserved, native integers are accepted as-is, and strings
    are converted through ``int()`` so explicit overrides and environment
    values follow the same normalisation path.

    Raises
    ------
    GlpiValidationError
        If a string value cannot be parsed as an integer (e.g.
        ``GLPI_TIMEOUT=abc``).
    TypeError
        If ``value`` is neither ``None``, ``int``, nor ``str``.
    """

    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise GlpiValidationError(
                f"Invalid integer environment value: {value!r}"
            ) from exc
    raise TypeError("Integer environment values must be strings or integers")


def parse_optional_env_bool(value: object, *, default: bool) -> bool:
    """Parse one optional boolean from an environment-style value.

    String values follow the conventional true and false spellings accepted
    by the package configuration helpers, while ``None`` falls back to the
    caller-provided default.
    """

    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        raise TypeError("Boolean environment values must be strings or booleans")
    if value.casefold() in {"1", "true", "yes", "on"}:
        return True
    if value.casefold() in {"0", "false", "no", "off"}:
        return False
    raise GlpiValidationError(f"Invalid boolean environment value: {value!r}")


def build_client_env_config(
    *,
    prefix: str,
    env: Mapping[str, str],
    overrides: Mapping[str, object],
) -> dict[str, object]:
    """Build common GLPI client config values from environment variables.

    The returned mapping matches the constructor keyword arguments accepted
    by :class:`GlpiClient`, making it suitable for direct unpacking.
    """

    config: dict[str, object] = {
        "glpi_api_url": env.get(f"{prefix}API_URL"),
        "client_id": env.get(f"{prefix}CLIENT_ID"),
        "client_secret": env.get(f"{prefix}CLIENT_SECRET"),
        "username": env.get(f"{prefix}USERNAME"),
        "password": env.get(f"{prefix}PASSWORD"),
        "glpi_entity": parse_optional_env_int(env.get(f"{prefix}ENTITY")),
        "glpi_profile": parse_optional_env_int(env.get(f"{prefix}PROFILE")),
        "entity_recursive": parse_optional_env_bool(
            env.get(f"{prefix}ENTITY_RECURSIVE"),
            default=False,
        ),
        "language": env.get(f"{prefix}LANGUAGE") or "en_GB",
        "verify_ssl": parse_optional_env_bool(
            env.get(f"{prefix}VERIFY_SSL"),
            default=True,
        ),
        "auth_token_refresh": parse_optional_env_int(
            env.get(f"{prefix}AUTH_TOKEN_REFRESH")
        ),
        "v1_base_url": env.get(f"{prefix}V1_BASE_URL"),
        "v1_user_token": env.get(f"{prefix}V1_USER_TOKEN"),
        "v1_app_token": env.get(f"{prefix}V1_APP_TOKEN"),
    }
    config.update(overrides)
    return config


def normalize_client_api_url(glpi_api_url: object, *, client_name: str) -> str:
    """Validate and normalise the configured GLPI API base URL.

    The helper rejects missing or non-string values early and strips a
    trailing slash so endpoint assembly remains consistent across the
    client codebase.
    """

    if not isinstance(glpi_api_url, str) or not glpi_api_url:
        raise GlpiValidationError(f"{client_name} requires glpi_api_url")
    return glpi_api_url.rstrip("/")


def validate_v1_document_config(
    *,
    v1_base_url: str | None,
    v1_user_token: str | None,
) -> None:
    """Validate the paired legacy v1 document configuration values.

    Document uploads require both the legacy base URL and the user token.
    The helper rejects partial configuration before a client is constructed.
    """

    if bool(v1_base_url) != bool(v1_user_token):
        raise GlpiValidationError(
            "GLPI v1 document support requires both v1_base_url and v1_user_token."
        )


__all__ = [
    "ClientResources",
    "build_client_env_config",
    "build_client_resources",
    "configure_ssl_warning_policy",
    "normalize_client_api_url",
    "parse_optional_env_bool",
    "parse_optional_env_int",
    "validate_v1_document_config",
]
