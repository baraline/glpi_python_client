"""HTTP transport helpers shared across the GLPI v2 API mixins.

The functions here normalise query parameters, build authenticated headers,
assemble request URLs, and validate responses so the per-endpoint mixins
can focus on resource-specific behaviour.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

import httpx

from glpi_python_client._errors import (
    GlpiProtocolError,
    GlpiServerError,
    GlpiTimeoutError,
    GlpiTransportError,
    status_error_class,
)
from glpi_python_client.clients.commons._constants import RequestParamValue


def transport_error_from(
    exc: httpx.HTTPError,
    *,
    method: str,
    url: str,
) -> GlpiTransportError:
    """Map one transport-level failure onto the library's public error type.

    Network faults are the last part of the failure surface that still
    escaped as third-party exceptions. Translating them here means callers
    catch :class:`~glpi_python_client.GlpiError` and never have to import the
    HTTP library, which is what :class:`~glpi_python_client.GlpiTransportError`
    was reserved for.

    It also removes a whole class of silent breakage. Retry predicates used
    to name the HTTP library's own exception base; because those trees are
    completely disjoint between libraries, swapping the transport without
    editing every predicate made retries stop matching — silently, with no
    error and a green test suite. Predicates now name this library-owned type
    instead, so a future transport change cannot invalidate them.

    Parameters
    ----------
    exc : httpx.HTTPError
        The transport failure to translate.
    method : str
        HTTP verb, used only to build the message.
    url : str
        Absolute URL of the failed request, used only to build the message.

    Returns
    -------
    GlpiTransportError
        :class:`~glpi_python_client.GlpiTimeoutError` when the failure was a
        timeout, otherwise :class:`~glpi_python_client.GlpiTransportError`.
        The original exception should be attached with ``raise ... from exc``
        by the caller.
    """

    error_class = (
        GlpiTimeoutError
        if isinstance(exc, httpx.TimeoutException)
        else GlpiTransportError
    )
    return error_class(
        f"GLPI {method.upper()} {url} failed: {type(exc).__name__}: {exc}"
    )


def response_reason(response: httpx.Response) -> str:
    """Return one response's HTTP reason phrase, whatever the transport.

    ``httpx`` spells this ``Response.reason_phrase``; ``requests`` spelled it
    ``Response.reason``. Both spellings are probed so the helper keeps
    working for the duck-typed response fakes in downstream test suites,
    which were written against the older attribute name.

    Parameters
    ----------
    response : httpx.Response
        Response to read the reason phrase from. Typed against the current
        transport; any object exposing either attribute works at runtime.

    Returns
    -------
    str
        The reason phrase, or ``""`` when the transport supplies none.
    """

    reason = getattr(response, "reason", None)
    if reason is None:
        reason = getattr(response, "reason_phrase", None)
    return str(reason) if reason else ""


def request_params(
    params: dict[str, object] | None,
) -> dict[str, RequestParamValue] | None:
    """Normalise query parameters into transport-compatible values.

    Each value is converted through :func:`request_param_value` so callers
    can pass richer Python objects without repeating serialisation logic.

    Keys whose value is ``None`` are **dropped** rather than forwarded. This
    is deliberate and load-bearing: ``requests`` omitted such keys from the
    query string entirely, whereas ``httpx`` encodes them as a valueless
    ``key=``. Sending an empty value to GLPI is not a no-op — an empty filter
    or search value is interpreted as "match everything", so forwarding the
    key would silently widen a query instead of leaving it unconstrained.
    Normalising here keeps the emitted query string identical across
    transports.
    """

    if params is None:
        return None
    return {
        key: request_param_value(value)
        for key, value in params.items()
        if value is not None
    }


def request_param_value(value: object) -> RequestParamValue:
    """Normalise one query parameter value for the HTTP transport.

    Values are rendered exactly as the previous ``requests``-based transport
    rendered them, so the wire format does not depend on which HTTP library
    is installed. Two conversions exist only to preserve that:

    * ``bytes`` are decoded to text. ``httpx`` would otherwise stringify the
      object itself and emit the Python repr (``b'x'``) rather than its
      contents.
    * ``bool`` is rendered ``"True"``/``"False"``. ``httpx`` renders booleans
      lowercase; ``requests`` did not. This is checked before ``int``
      because ``bool`` is a subclass of ``int``.
    """

    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int | float):
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
    response: httpx.Response,
    *,
    method: str,
    url: str,
    success_statuses: tuple[int, ...],
    logger: logging.Logger,
) -> httpx.Response:
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
            f"{response.status_code} {response_reason(response)}"
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
    response: httpx.Response,
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


def response_json_or_empty(response: httpx.Response) -> object:
    """Return the parsed JSON body or an empty mapping for empty responses.

    Unlike :func:`response_json_mapping` this helper preserves list and
    scalar payloads, so it suits callers that may receive either a JSON
    object or a JSON array (for example the legacy v1 endpoints).
    """

    if not response.content or not response.text.strip():
        return {}
    return response.json()


def response_json_mapping(response: httpx.Response) -> Mapping[str, object]:
    """Return the JSON response payload as a mapping when possible.

    Empty response bodies become an empty mapping and non-mapping JSON
    payloads are intentionally ignored so callers can safely probe for
    expected keys.
    """

    result = response.json() if response.content else {}
    return result if isinstance(result, Mapping) else {}


def require_response_int(
    response: httpx.Response,
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
    "transport_error_from",
    "unwrap_timeline_items",
]
