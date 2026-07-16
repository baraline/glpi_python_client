"""Unit tests for the public exception hierarchy."""

from __future__ import annotations

import copy
import pickle

import pytest

from glpi_python_client import (
    GlpiAuthError,
    GlpiError,
    GlpiNotFoundError,
    GlpiProtocolError,
    GlpiServerError,
    GlpiStatusError,
    GlpiTimeoutError,
    GlpiTransportError,
    GlpiValidationError,
)
from glpi_python_client._errors import status_error_class


def test_every_public_error_derives_from_glpi_error() -> None:
    """One ``except GlpiError`` catches the whole library surface."""

    for cls in (
        GlpiTransportError,
        GlpiTimeoutError,
        GlpiStatusError,
        GlpiAuthError,
        GlpiNotFoundError,
        GlpiServerError,
        GlpiValidationError,
        GlpiProtocolError,
    ):
        assert issubclass(cls, GlpiError)


def test_timeout_is_a_transport_error() -> None:
    """``GlpiTimeoutError`` narrows ``GlpiTransportError``."""

    assert issubclass(GlpiTimeoutError, GlpiTransportError)


def test_transport_errors_are_not_value_errors() -> None:
    """A transport fault is not a caller mistake, so it is not a ``ValueError``."""

    assert not issubclass(GlpiTransportError, ValueError)


@pytest.mark.parametrize(
    "cls", [GlpiStatusError, GlpiValidationError, GlpiProtocolError]
)
def test_value_error_back_compat(cls: type[Exception]) -> None:
    """Callers written against the old bare-``ValueError`` contract keep working."""

    assert issubclass(cls, ValueError)


def test_status_error_carries_diagnostics_and_preserves_message() -> None:
    """``GlpiStatusError`` exposes status/url/body and keeps ``str(e)`` intact."""

    error = GlpiStatusError(
        "Failed to fetch ticket 1: 404 nope",
        status_code=404,
        url="https://glpi.example.test/api.php/Assistance/Ticket/1",
        response_text="nope",
    )
    assert error.status_code == 404
    assert error.url == "https://glpi.example.test/api.php/Assistance/Ticket/1"
    assert error.response_text == "nope"
    assert str(error) == "Failed to fetch ticket 1: 404 nope"


def test_status_error_response_text_defaults_to_empty() -> None:
    """``response_text`` is optional."""

    error = GlpiStatusError("boom", status_code=500, url="https://x")
    assert error.response_text == ""


def test_status_error_is_catchable_as_value_error_with_match() -> None:
    """Legacy ``pytest.raises(ValueError, match=...)`` assertions still fire."""

    with pytest.raises(ValueError, match="404 nope"):
        raise GlpiNotFoundError(
            "Failed to fetch ticket 1: 404 nope",
            status_code=404,
            url="https://x",
            response_text="nope",
        )


def test_status_error_survives_pickle_round_trip() -> None:
    """Keyword-only arguments do not break ``pickle`` (used across processes)."""

    error = GlpiServerError(
        "boom", status_code=503, url="https://x", response_text="down"
    )
    restored = pickle.loads(pickle.dumps(error))
    assert isinstance(restored, GlpiServerError)
    assert restored.status_code == 503
    assert restored.url == "https://x"
    assert restored.response_text == "down"
    assert str(restored) == "boom"


def test_status_error_survives_copy() -> None:
    """``copy.copy`` uses the same reduce protocol as pickle."""

    error = GlpiAuthError("nope", status_code=401, url="https://x")
    assert copy.copy(error).status_code == 401


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, GlpiAuthError),
        (403, GlpiAuthError),
        (404, GlpiNotFoundError),
        (500, GlpiServerError),
        (503, GlpiServerError),
        (599, GlpiServerError),
        (418, GlpiStatusError),
        (400, GlpiStatusError),
    ],
)
def test_status_error_class_dispatch(
    status_code: int, expected: type[GlpiStatusError]
) -> None:
    """``status_error_class`` maps each status band to its narrowest class."""

    assert status_error_class(status_code) is expected
