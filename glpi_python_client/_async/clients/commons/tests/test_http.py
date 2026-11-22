"""Unit tests for :mod:`glpi_python_client._async.clients.commons._http`.

The tests cover the small request and response helper utilities used by the
transport and the per-endpoint mixins.
"""

from __future__ import annotations

import json

import httpx
import pytest

from glpi_python_client import (
    GlpiNotFoundError,
    GlpiProtocolError,
    GlpiResponseBodyError,
    GlpiValidationError,
)
from glpi_python_client._async.clients.commons._http import (
    build_request_headers,
    build_request_url,
    decode_json_body,
    ensure_response_status,
    list_payload_items,
    request_param_value,
    request_params,
    require_access_token,
    require_response_int,
    response_json_mapping,
    response_json_or_empty,
)
from glpi_python_client.testing.utils import FakeResponse


def test_request_param_value_normalises_supported_types() -> None:
    """The helper renders every value the way the wire format expects.

    Numbers and strings pass through untouched. ``bool`` and ``bytes`` are
    converted deliberately, because the underlying HTTP libraries disagree
    about them: ``httpx`` renders booleans lowercase and stringifies a
    ``bytes`` object into its Python repr (``b'x'``), where the previous
    ``requests``-based transport emitted ``True`` and the decoded text.
    Normalising here keeps the emitted query string identical regardless of
    which library is installed.
    """

    assert request_param_value(7) == 7
    assert request_param_value(1.5) == 1.5
    assert request_param_value("hello") == "hello"
    assert request_param_value(True) == "True"
    assert request_param_value(False) == "False"
    assert request_param_value(b"raw") == "raw"
    assert request_param_value(object()) != ""


def test_request_params_drops_none_values() -> None:
    """``None`` parameter values are excluded from the produced query mapping.

    This is a correctness guarantee, not a tidiness one. ``requests`` omitted
    a ``None``-valued key from the query string entirely; ``httpx`` encodes it
    as a valueless ``key=``. GLPI does not treat those the same — an empty
    filter or search value matches *everything* — so forwarding the key would
    silently widen a query rather than leave it unconstrained.
    """

    cleaned = request_params({"limit": 10, "filter": None, "force": True})
    assert cleaned == {"limit": 10, "force": "True"}
    assert "filter" not in cleaned


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


def test_4xx_raises_a_typed_status_error_from_ensure_response_status() -> None:
    """The 4xx raise stays in ``ensure_response_status`` and is typed."""

    response = FakeResponse(status_code=404, payload={}, text="nope")
    with pytest.raises(GlpiNotFoundError) as excinfo:
        ensure_response_status(
            response,
            success_statuses=(200, 206),
            failure_message="Failed to fetch ticket 1",
        )

    assert excinfo.value.status_code == 404
    assert isinstance(excinfo.value, ValueError)
    assert str(excinfo.value) == "Failed to fetch ticket 1: 404 nope"


def test_require_response_int_accepts_a_numeric_string_id() -> None:
    """A quoted identifier is still an identifier.

    GLPI is PHP-backed and PHP-backed APIs commonly render integers as
    strings. Rejecting one is a protocol error raised over a usable value.
    """

    response = FakeResponse(payload={"id": "4242"})

    assert require_response_int(response, keys=("id",), missing_message="x") == 4242


def test_require_response_int_ignores_a_non_numeric_string_id() -> None:
    """A string that is not a number is not silently coerced."""

    response = FakeResponse(payload={"id": "not-a-number"})

    with pytest.raises(GlpiProtocolError):
        require_response_int(response, keys=("id",), missing_message="x")


def test_require_response_int_reads_a_nested_data_envelope() -> None:
    """An id wrapped in a ``data`` envelope is found rather than refused."""

    response = FakeResponse(payload={"data": {"id": 4242}})

    assert require_response_int(response, keys=("id",), missing_message="x") == 4242


def test_require_response_int_falls_back_to_the_location_header() -> None:
    """A 201 whose id lives only in ``Location`` still yields the id.

    A create that answers with an empty body and a resource URL is a normal
    REST shape; without this the client raises a protocol error on a request
    that succeeded, and the caller loses the id of a record that now exists.
    """

    response = FakeResponse(
        status_code=201,
        payload=None,
        content=b"",
        headers={
            "Location": "https://glpi.example.test/api.php/v2/Assistance/Ticket/4242"
        },
    )

    assert require_response_int(response, keys=("id",), missing_message="x") == 4242


_BODY_URL = "https://glpi.example.test/api.php/Assistance/Ticket/1"


def _body_response(
    content: bytes, *, content_type: str = "text/html", status: int = 200
) -> httpx.Response:
    """Build a real ``httpx`` response, so ``json()`` really tries to decode."""

    return httpx.Response(
        status,
        content=content,
        headers={"content-type": content_type},
        request=httpx.Request("GET", _BODY_URL),
    )


@pytest.mark.parametrize(
    ("content", "content_type"),
    [
        (b"<html><body>Bad gateway page</body></html>", "text/html; charset=utf-8"),
        (b"\xff\xfe\x00garbled", "application/json"),
        (b"", "application/json"),
    ],
)
def test_decode_json_body_raises_protocol_error_on_an_unusable_body(
    content: bytes, content_type: str
) -> None:
    """A success body that is not JSON is the response's fault, not a bad value."""

    response = _body_response(content, content_type=content_type)
    with pytest.raises(GlpiResponseBodyError) as excinfo:
        decode_json_body(response)

    error = excinfo.value
    assert isinstance(error, GlpiProtocolError)
    assert isinstance(error.__cause__, (json.JSONDecodeError, UnicodeDecodeError))
    assert error.status_code == 200
    assert error.url == _BODY_URL
    assert error.content_type == content_type
    assert error.body_length == len(content)


def test_decode_json_body_bounds_the_excerpt_and_keeps_it_out_of_the_message() -> None:
    """The body may carry data: it is kept as a bounded attribute only."""

    content = b"<html>" + b"x" * 5000
    with pytest.raises(GlpiResponseBodyError) as excinfo:
        decode_json_body(_body_response(content))

    assert excinfo.value.body_excerpt == content[:200].decode()
    assert "xxxx" not in str(excinfo.value)
    assert str(excinfo.value.status_code) in str(excinfo.value)


def test_decode_json_body_returns_valid_json_untouched() -> None:
    assert decode_json_body(_body_response(b'{"id": 1}', content_type="a/b")) == {
        "id": 1
    }


def test_lenient_helpers_keep_an_empty_body_empty_but_reject_html() -> None:
    """Deliberately empty answers stay empty; a non-empty non-JSON body raises."""

    assert response_json_or_empty(_body_response(b"")) == {}
    assert response_json_mapping(_body_response(b"")) == {}
    with pytest.raises(GlpiResponseBodyError):
        response_json_or_empty(_body_response(b"<html></html>"))
    with pytest.raises(GlpiResponseBodyError):
        response_json_mapping(_body_response(b"<html></html>"))


def test_response_body_error_survives_pickle_round_trip() -> None:
    import pickle

    error = GlpiResponseBodyError(
        "boom",
        status_code=200,
        url="https://x",
        content_type="text/html",
        body_length=7,
        body_excerpt="<html>",
    )
    clone = pickle.loads(pickle.dumps(error))
    assert (clone.status_code, clone.url, clone.content_type) == (
        200,
        "https://x",
        "text/html",
    )
    assert (clone.body_length, clone.body_excerpt, str(clone)) == (7, "<html>", "boom")
