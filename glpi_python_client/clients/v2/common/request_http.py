"""HTTP request and response helpers for GLPI v2 clients.

This module contains the small transport-agnostic helpers used by both sync
and async request layers to normalize parameters, assemble headers, and handle
common response validation rules.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

import requests

from glpi_python_client.content.records.core.scalars import _optional_text

from .constants import RequestParamValue


def request_params(
    params: dict[str, object] | None,
) -> dict[str, RequestParamValue] | None:
    """Normalize query parameters into ``requests``-compatible values.

    Each value is converted through ``request_param_value`` so callers can pass
    richer Python objects without repeating serialization logic.
    """

    if params is None:
        return None
    return {key: request_param_value(value) for key, value in params.items()}


def request_param_value(value: object) -> RequestParamValue:
    """Normalize one query parameter value for ``requests``.

    Native scalar values are preserved and any other object is stringified so
    higher-level client code can pass enums and IDs without special handling.
    """

    if value is None or isinstance(value, str | int | float | bytes):
        return value
    return str(value)


def require_access_token(access_token: str | None) -> str:
    """Return a usable access token or raise when it is missing.

    Transport helpers call this right before request dispatch so missing token
    state turns into a clear local error instead of a malformed API call.
    """

    if not access_token:
        raise ValueError("Failed to acquire access token for API request")
    return access_token


def build_request_headers(
    *,
    access_token: str | None,
    language: str,
    glpi_entity: int | None,
    glpi_profile: int | None,
    entity_recursive: bool,
    include_content_type: bool = False,
    skip_entity: bool = False,
) -> dict[str, str]:
    """Build GLPI request headers from one client state snapshot.

    The header set includes authorization and language settings, with optional
    entity, profile, recursion, and content-type headers derived from the
    current client configuration.
    """

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Accept-Language": language,
    }
    if include_content_type:
        headers["Content-Type"] = "application/json"
    if not skip_entity:
        if glpi_entity is not None:
            headers["GLPI-Entity"] = str(glpi_entity)
        if glpi_profile is not None:
            headers["GLPI-Profile"] = str(glpi_profile)
        if entity_recursive:
            headers["GLPI-Entity-Recursive"] = "true"
    return headers


def build_request_url(glpi_api_url: str, endpoint: str) -> str:
    """Return the absolute URL for one GLPI endpoint path.

    Callers provide the normalized API base URL and the endpoint suffix that is
    already specific to the requested resource.
    """

    return f"{glpi_api_url}/{endpoint}"


def finalize_request_response(
    response: requests.Response,
    *,
    method: str,
    url: str,
    success_statuses: tuple[int, ...],
    logger: logging.Logger,
) -> requests.Response:
    """Validate one GLPI transport response and preserve warning behavior.

    Server errors are raised immediately while non-success statuses outside the
    accepted set are logged for higher-level mutation and lookup helpers to
    interpret consistently.
    """

    method_name = method.upper()
    if 500 <= response.status_code < 600:
        message = (
            f"GLPI {method_name} {url} failed with "
            f"{response.status_code} {response.reason}"
        )
        logger.warning(message)
        raise requests.HTTPError(message)
    if response.status_code not in success_statuses:
        logger.warning(
            "GLPI %s %s returned %s: %s",
            method_name,
            url,
            response.status_code,
            response.text[:200],
        )
    return response


def ensure_response_status(
    response: requests.Response,
    *,
    success_statuses: tuple[int, ...],
    failure_message: str,
) -> None:
    """Raise a consistent ``ValueError`` for an unexpected response status.

    Higher-level client methods use this helper to keep their mutation and fetch
    failure messages aligned across sync and async call sites.
    """

    if response.status_code not in success_statuses:
        raise ValueError(
            f"{failure_message}: {response.status_code} {response.text[:200]}"
        )


def response_json_mapping(response: requests.Response) -> Mapping[str, object]:
    """Return the JSON response payload as a mapping when possible.

    Empty response bodies become an empty mapping and non-mapping JSON payloads
    are intentionally ignored so callers can safely probe expected keys.
    """

    result = response.json() if response.content else {}
    return result if isinstance(result, Mapping) else {}


def require_response_text(
    response: requests.Response,
    *,
    keys: tuple[str, ...],
    missing_message: str,
) -> str:
    """Return the first non-empty text field from a JSON response mapping.

    This is primarily used for create responses that may expose the created ID
    under one of several field names.
    """

    result = response_json_mapping(response)
    for key in keys:
        value = _optional_text(result.get(key))
        if value is not None:
            return value
    raise ValueError(missing_message)


def require_non_empty_text(value: object, *, error_message: str) -> str:
    """Return stripped text or raise when the value is empty.

    Validation stays centralized here so operation-level preconditions use the
    same message and whitespace-trimming behavior throughout the package.
    """

    text = _optional_text(value)
    if text is None:
        raise ValueError(error_message)
    return text
