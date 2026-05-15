"""Unit tests for :mod:`glpi_python_client.clients.commons._filters`."""

from __future__ import annotations

from glpi_python_client.clients.commons._filters import (
    escape_rsql_like_value,
    escape_rsql_text_value,
    rsql_all_filter,
    rsql_any_filter,
    rsql_contains_filter,
    rsql_equals_filter,
)


def test_rsql_equals_filter_quotes_strings() -> None:
    """``rsql_equals_filter`` quotes string values for the GLPI RSQL syntax."""

    assert rsql_equals_filter("name", "alice") == 'name=="alice"'


def test_rsql_contains_filter_uses_like_operator() -> None:
    """``rsql_contains_filter`` uses the GLPI ``=like=`` operator with wildcards."""

    expression = rsql_contains_filter("name", "ali")
    assert expression == 'name=like="*ali*"'


def test_rsql_all_filter_joins_with_semicolons() -> None:
    """``rsql_all_filter`` joins non-empty parts with ``;``."""

    assert rsql_all_filter("a==1", "", "b==2") == "a==1;b==2"


def test_rsql_any_filter_joins_with_commas() -> None:
    """``rsql_any_filter`` joins non-empty parts with ``,``."""

    assert rsql_any_filter("a==1", None, "b==2") == "a==1,b==2"


def test_escape_rsql_like_value_escapes_special_characters() -> None:
    """The helper escapes the wildcard and quote characters used by RSQL."""

    assert escape_rsql_like_value('a*b"c') == 'a\\*b\\"c'


def test_escape_rsql_text_value_escapes_quotes() -> None:
    """``escape_rsql_text_value`` escapes double quotes inside the literal."""

    assert escape_rsql_text_value('a"b') == 'a\\"b'
