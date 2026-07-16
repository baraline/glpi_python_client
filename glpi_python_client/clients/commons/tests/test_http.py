"""Unit tests for :mod:`glpi_python_client.clients.commons._http`.

The tests cover the small request and response helper utilities used by the
asynchronous transport and the per-endpoint mixins.
"""

from __future__ import annotations

import json

import pytest

from glpi_python_client import GlpiProtocolError, GlpiValidationError
from glpi_python_client.clients.commons._http import (
    build_request_headers,
    build_request_url,
    ensure_response_status,
    list_payload_items,
    request_param_value,
    request_params,
    require_access_token,
    require_response_int,
    response_json_mapping,
)
from glpi_python_client.testing.utils import FakeResponse


def test_request_param_value_normalises_supported_types() -> None:
    """The helper returns native scalar values unchanged and stringifies others."""

    assert request_param_value(True) is True
    assert request_param_value(7) == 7
    assert request_param_value("hello") == "hello"
    assert request_param_value(object()) != ""


def test_request_params_drops_none_values() -> None:
    """``None`` parameter values are excluded from the produced query mapping."""

    cleaned = request_params({"limit": 10, "filter": None, "force": True})
    assert cleaned == {"limit": 10, "filter": None, "force": True}


def test_build_request_url_concatenates_base_and_endpoint() -> None:
    """The helper joins the base URL and endpoint with a single slash."""

    assert (
        build_request_url("https://glpi.test/api/v2", "Assistance/Ticket")
        == "https://glpi.test/api/v2/Assistance/Ticket"
    )


def test_build_request_headers_include_entity_when_not_skipped() -> None:
    """The default headers include the ``GLPI-Entity`` header when configured."""

    headers = build_request_headers(
        access_token="token",
        language="fr_FR",
        glpi_entity=12,
        glpi_profile=4,
        entity_recursive=True,
        include_content_type=True,
        skip_entity=False,
    )
    assert headers["Authorization"] == "Bearer token"
    assert headers["Content-Type"] == "application/json"
    assert headers["GLPI-Entity"] == "12"
    assert headers["GLPI-Entity-Recursive"] == "true"
    assert headers["GLPI-Profile"] == "4"
    assert headers["Accept-Language"] == "fr_FR"


def test_build_request_headers_skip_entity_drops_entity_headers() -> None:
    """When ``skip_entity`` is true the entity headers are omitted."""

    headers = build_request_headers(
        access_token="token",
        language="en_GB",
        glpi_entity=12,
        glpi_profile=None,
        entity_recursive=False,
        skip_entity=True,
    )
    assert "GLPI-Entity" not in headers
    assert "GLPI-Entity-Recursive" not in headers


def test_require_access_token_rejects_missing_value() -> None:
    """``require_access_token`` raises when the token is missing or empty."""

    with pytest.raises(ValueError):
        require_access_token(None)


def test_ensure_response_status_raises_for_unexpected_status() -> None:
    """``ensure_response_status`` raises when the status is not whitelisted."""

    response = FakeResponse(status_code=500, payload={"error": "boom"})
    with pytest.raises(ValueError):
        ensure_response_status(
            response,
            success_statuses=(200,),
            failure_message="Boom",
        )


def test_response_json_mapping_returns_dict() -> None:
    """``response_json_mapping`` returns the JSON body when it is a mapping."""

    response = FakeResponse(payload={"a": 1})
    assert response_json_mapping(response) == {"a": 1}


def test_require_response_int_returns_first_matching_key() -> None:
    """``require_response_int`` returns the first integer-typed value."""

    response = FakeResponse(payload={"id": 42})
    assert require_response_int(response, keys=("id",), missing_message="x") == 42


def test_list_payload_items_handles_dict_payload() -> None:
    """``list_payload_items`` returns an empty list for non-list payloads."""

    assert list_payload_items({"data": [1, 2, 3]}) == []
    assert list_payload_items([{"id": 1}, 2]) == [{"id": 1}]


def test_fake_response_round_trip() -> None:
    """The shared ``FakeResponse`` test helper round-trips JSON payloads."""

    response = FakeResponse(payload={"hello": "world"})
    assert json.loads(response.text.replace("'", '"')) == {"hello": "world"}


def test_require_access_token_raises_protocol_error_when_missing() -> None:
    """A missing token means the OAuth response was unusable, not a caller error."""

    with pytest.raises(GlpiProtocolError) as excinfo:
        require_access_token(None)

    assert isinstance(excinfo.value, ValueError)
    assert str(excinfo.value) == "Failed to acquire access token for API request"


def test_require_response_int_raises_protocol_error_when_id_missing() -> None:
    """A 2xx create response without a numeric id is a protocol failure."""

    response = FakeResponse(status_code=201, payload={"nope": "x"})
    with pytest.raises(GlpiProtocolError) as excinfo:
        require_response_int(
            response, keys=("id",), missing_message="GLPI create returned no id"
        )

    assert isinstance(excinfo.value, ValueError)
    assert str(excinfo.value) == "GLPI create returned no id"


def test_protocol_error_is_not_a_validation_error() -> None:
    """A server-shape fault must not masquerade as a caller mistake."""

    assert not issubclass(GlpiProtocolError, GlpiValidationError)
