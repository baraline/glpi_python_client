"""HTTP transport helpers shared across the GLPI v2 API mixins.

The functions here normalise query parameters, build authenticated headers,
assemble request URLs, and validate responses so the per-endpoint mixins
can focus on resource-specific behaviour.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

import requests

from glpi_python_client._errors import (
    GlpiProtocolError,
    GlpiServerError,
    status_error_class,
)
from glpi_python_client.clients.commons._constants import RequestParamValue


def request_params(
    params: dict[str, object] | None,
) -> dict[str, RequestParamValue] | None:
    """Normalise query parameters into ``requests``-compatible values.

    Each value is converted through :func:`request_param_value` so callers
    can pass richer Python objects without repeating serialisation logic.
    """

    if params is None:
        return None
    return {key: request_param_value(value) for key, value in params.items()}


def request_param_value(value: object) -> RequestParamValue:
    """Normalise one query parameter value for ``requests``.

    Native scalar values are preserved and any other object is stringified
    so higher-level client code can pass enums and identifiers without
    special handling.
    """

    if value is None or isinstance(value, str | int | float | bytes):
        return value
    return str(value)


def require_access_token(access_token: str | None) -> str:
    """Return a usable access token or raise when it is missing.

    Transport helpers call this right before request dispatch so missing
    token state turns into a clear local error instead of a malformed API
    call.

    Raises
    ------
    GlpiProtocolError
        When ``access_token`` is empty or ``None``.
    """

    if not access_token:
        raise GlpiProtocolError("Failed to acquire access token for API request")
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

    The header set includes authorisation and language settings, with
    optional entity, profile, recursion, and content-type headers derived
    from the current client configuration.
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

    Callers provide the normalised API base URL and the endpoint suffix
    that is already specific to the requested resource.
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
    """Validate one GLPI transport response and preserve warning behaviour.

    Server errors are raised immediately while non-success statuses outside
    the accepted set are logged for higher-level mutation and lookup helpers
    to interpret consistently.

    Raises
    ------
    GlpiServerError
        When ``response.status_code`` is a 5xx server error.
    """

    method_name = method.upper()
    if 500 <= response.status_code < 600:
        message = (
            f"GLPI {method_name} {url} failed with "
            f"{response.status_code} {response.reason}"
        )
        logger.warning(message)
        raise GlpiServerError(
            message,
            status_code=response.status_code,
            url=url,
            response_text=response.text,
        )
    if response.status_code not in success_statuses:
        logger.warning(
            "GLPI %s %s returned %s: %s",
            method_name,
            url,
            response.status_code,
            response.text,
        )
    return response


def ensure_response_status(
    response: requests.Response,
    *,
    success_statuses: tuple[int, ...],
    failure_message: str,
) -> None:
    """Raise a typed :class:`GlpiStatusError` for an unexpected response status.

    Higher-level client methods use this helper to keep their mutation and
    fetch failure messages aligned across the per-endpoint mixins. The
    raised class narrows to :class:`GlpiAuthError`, :class:`GlpiNotFoundError`
    or :class:`GlpiServerError` where the status allows it.

    Raises
    ------
    GlpiStatusError
        When ``response.status_code`` is outside ``success_statuses``.
    """

    if response.status_code not in success_statuses:
        error_class = status_error_class(response.status_code)
        raise error_class(
            f"{failure_message}: {response.status_code} {response.text}",
            status_code=response.status_code,
            url=str(response.url),
            response_text=response.text,
        )


def response_json_or_empty(response: requests.Response) -> object:
    """Return the parsed JSON body or an empty mapping for empty responses.

    Unlike :func:`response_json_mapping` this helper preserves list and
    scalar payloads, so it suits callers that may receive either a JSON
    object or a JSON array (for example the legacy v1 endpoints).
    """

    if not response.content or not response.text.strip():
        return {}
    return response.json()


def response_json_mapping(response: requests.Response) -> Mapping[str, object]:
    """Return the JSON response payload as a mapping when possible.

    Empty response bodies become an empty mapping and non-mapping JSON
    payloads are intentionally ignored so callers can safely probe for
    expected keys.
    """

    result = response.json() if response.content else {}
    return result if isinstance(result, Mapping) else {}


def require_response_int(
    response: requests.Response,
    *,
    keys: tuple[str, ...],
    missing_message: str,
) -> int:
    """Return the first integer field from a JSON response mapping.

    GLPI v2 create responses document numeric identifiers under a small
    set of keys. Callers list the candidate keys explicitly so the
    behaviour stays predictable.

    Raises
    ------
    GlpiProtocolError
        When none of ``keys`` maps to an integer value in the response.
    """

    result = response_json_mapping(response)
    for key in keys:
        value = result.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    raise GlpiProtocolError(missing_message)


def list_payload_items(payload: object) -> list[dict[str, object]]:
    """Return dictionary items from one plain JSON list payload.

    Non-list payloads are treated as empty so callers can safely use this
    on responses whose shape may vary or fail validation upstream.
    """

    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def unwrap_timeline_items(payload: object) -> list[dict[str, object]]:
    """Return inner records from a GLPI timeline list payload.

    Notes
    -----
    The OpenAPI contract documents
    ``/Assistance/Ticket/{id}/Timeline/<Subitem>`` GET responses as flat
    arrays of the subitem schema, but the live GLPI v2 server actually
    returns each entry wrapped in an envelope of the form
    ``{"type": "<Subitem>", "item": {...}}``. The helper unwraps that
    envelope when present and falls back to the flat shape so it stays
    compatible with both behaviours. Per the project rule that real
    behaviour wins over the contract, the timeline list helpers call this
    helper instead of :func:`list_payload_items`.
    """

    if not isinstance(payload, list):
        return []
    items: list[dict[str, object]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        if "item" in entry and isinstance(entry["item"], dict):
            items.append(entry["item"])
        else:
            items.append(entry)
    return items


__all__ = [
    "build_request_headers",
    "build_request_url",
    "ensure_response_status",
    "finalize_request_response",
    "list_payload_items",
    "request_param_value",
    "request_params",
    "require_access_token",
    "require_response_int",
    "response_json_mapping",
    "response_json_or_empty",
    "unwrap_timeline_items",
]
