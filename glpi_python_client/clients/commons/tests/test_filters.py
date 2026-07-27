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
    """``rsql_any_filter`` ORs parts and parenthesises the group."""

    assert rsql_any_filter("a==1", None, "b==2") == "(a==1,b==2)"


def test_rsql_any_filter_single_part_is_not_wrapped() -> None:
    """A lone fragment needs no group and is returned unchanged."""

    assert rsql_any_filter(None, "a==1", "") == "a==1"


def test_rsql_any_filter_group_survives_an_and_join() -> None:
    """The OR group keeps its AND clauses when nested in ``rsql_all_filter``.

    RSQL binds ``;`` tighter than ``,``. Without the parentheses this
    composes to ``date;e==1,e==2``, which the server reads as
    ``(date AND e==1) OR e==2`` -- so every ``e==2`` record matches
    regardless of the date window. Measured against a live GLPI 11
    instance, that returned 16,245 tickets where the correct answer,
    reproduced by the parenthesised form, was 1,552.
    """

    combined = rsql_all_filter(
        "date_creation=ge=2026-01-01",
        rsql_any_filter("entity.id==1", "entity.id==2"),
    )
    assert combined == "date_creation=ge=2026-01-01;(entity.id==1,entity.id==2)"


def test_escape_rsql_like_value_escapes_special_characters() -> None:
    """The helper escapes the wildcard and quote characters used by RSQL."""

    assert escape_rsql_like_value('a*b"c') == 'a\\*b\\"c'


def test_escape_rsql_text_value_escapes_quotes() -> None:
    """``escape_rsql_text_value`` escapes double quotes inside the literal."""

    assert escape_rsql_text_value('a"b') == 'a\\"b'
