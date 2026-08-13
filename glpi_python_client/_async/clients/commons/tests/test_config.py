"""Unit tests for client configuration parsing and validation.

These helpers normalise the API URL, validate the legacy v1 credential
pair, and coerce the GLPI_* environment variables. They are pure
functions: no client is constructed and nothing is awaited.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from glpi_python_client import GlpiValidationError
from glpi_python_client._async.clients.commons._config import (
    build_client_env_config,
    normalize_client_api_url,
    parse_optional_env_bool,
    parse_optional_env_int,
    resolve_server_timezone,
    validate_v1_document_config,
)


def test_normalize_client_api_url_strips_trailing_slash() -> None:
    """The helper trims one trailing slash for consistent endpoint joins."""

    assert (
        normalize_client_api_url("https://glpi.test/api.php/v2/", client_name="X")
        == "https://glpi.test/api.php/v2"
    )


def test_normalize_client_api_url_rejects_missing_value() -> None:
    """Missing or empty URL raises ``GlpiValidationError`` with the client name.

    ``GlpiValidationError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working.
    """

    with pytest.raises(GlpiValidationError, match="X requires glpi_api_url") as exc1:
        normalize_client_api_url(None, client_name="X")
    assert isinstance(exc1.value, ValueError)
    with pytest.raises(GlpiValidationError, match="X requires glpi_api_url") as exc2:
        normalize_client_api_url("", client_name="X")
    assert isinstance(exc2.value, ValueError)
    with pytest.raises(GlpiValidationError, match="X requires glpi_api_url") as exc3:
        normalize_client_api_url(123, client_name="X")  # type: ignore[arg-type]
    assert isinstance(exc3.value, ValueError)


def test_validate_v1_document_config_rejects_partial_pair() -> None:
    """Either both v1 values are present or both are absent.

    ``GlpiValidationError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working.
    """

    with pytest.raises(
        GlpiValidationError, match="v1_base_url and v1_user_token"
    ) as exc1:
        validate_v1_document_config(v1_base_url="https://x", v1_user_token=None)
    assert isinstance(exc1.value, ValueError)
    with pytest.raises(
        GlpiValidationError, match="v1_base_url and v1_user_token"
    ) as exc2:
        validate_v1_document_config(v1_base_url=None, v1_user_token="t")
    assert isinstance(exc2.value, ValueError)


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


def test_parse_optional_env_int_rejects_unparseable_string() -> None:
    """A non-numeric string (e.g. ``GLPI_TIMEOUT=abc``) raises ``GlpiValidationError``.

    ``GlpiValidationError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working, and the original ``int()``
    ``ValueError`` is chained via ``from`` rather than swallowed.
    """

    with pytest.raises(GlpiValidationError, match="abc") as excinfo:
        parse_optional_env_int("abc")
    assert isinstance(excinfo.value, ValueError)
    assert isinstance(excinfo.value.__cause__, ValueError)


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
    """Unknown strings raise ``GlpiValidationError``.

    ``GlpiValidationError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working.
    """

    with pytest.raises(GlpiValidationError) as excinfo:
        parse_optional_env_bool("maybe", default=False)
    assert isinstance(excinfo.value, ValueError)


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


def test_resolve_server_timezone_accepts_an_iana_name() -> None:
    """An IANA zone name resolves to a DST-aware timezone.

    A name rather than a fixed offset is what makes winter and summer both
    correct: the same GLPI instance sends ``+01:00`` and ``+02:00``.
    """

    resolved = resolve_server_timezone("Europe/Paris")

    assert datetime(2019, 1, 15, tzinfo=resolved).utcoffset() == timedelta(hours=1)
    assert datetime(2018, 7, 15, tzinfo=resolved).utcoffset() == timedelta(hours=2)


def test_resolve_server_timezone_passes_a_tzinfo_through() -> None:
    """A caller holding a tzinfo object may supply it directly."""

    fixed = timezone(timedelta(hours=2))

    assert resolve_server_timezone(fixed) is fixed


def test_resolve_server_timezone_rejects_an_unknown_name() -> None:
    """A typo fails at construction, not silently at the first timestamp."""

    with pytest.raises(GlpiValidationError) as excinfo:
        resolve_server_timezone("Europe/Pariss")

    assert "Europe/Pariss" in str(excinfo.value)


def test_resolve_server_timezone_rejects_a_missing_value() -> None:
    """The timezone is required; GLPI does not advertise it."""

    with pytest.raises(GlpiValidationError):
        resolve_server_timezone(None)


def test_resolve_server_timezone_rejects_a_blank_name() -> None:
    """An empty environment variable is a missing value, not a valid one."""

    with pytest.raises(GlpiValidationError):
        resolve_server_timezone("   ")
