"""Unit tests for the public RSQL date builders."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from glpi_python_client import GlpiValidationError
from glpi_python_client.rsql import changed_since, created_between, date_window


def test_created_between_builds_an_inclusive_window() -> None:
    """The window covers both endpoints, the end through end-of-day."""

    assert created_between(date(2026, 1, 1), date(2026, 1, 31)) == (
        "date_creation=ge=2026-01-01;date_creation=le=2026-01-31 23:59:59"
    )


def test_created_between_accepts_iso_strings() -> None:
    """ISO ``YYYY-MM-DD`` strings are accepted alongside date objects."""

    assert created_between("2026-01-01", "2026-01-31") == created_between(
        date(2026, 1, 1), date(2026, 1, 31)
    )


def test_created_between_accepts_a_single_day() -> None:
    """A one-day window is a legitimate window, not an empty one."""

    assert created_between(date(2026, 1, 1), date(2026, 1, 1)) == (
        "date_creation=ge=2026-01-01;date_creation=le=2026-01-01 23:59:59"
    )


def test_created_between_rejects_a_reversed_window() -> None:
    """A start after the end is a caller error, not an empty result set.

    GLPI answers a contradictory window with zero rows, which reads as "no
    tickets matched" rather than "your dates are backwards".
    """

    with pytest.raises(GlpiValidationError):
        created_between(date(2026, 1, 31), date(2026, 1, 1))


def test_created_between_rejects_a_malformed_date() -> None:
    """A string that is not an ISO date fails here, not on the server."""

    with pytest.raises(GlpiValidationError):
        created_between("31/01/2026", "2026-01-31")


def test_date_window_targets_any_field() -> None:
    """The field is a parameter so the same grammar serves other columns."""

    assert date_window("date_mod", date(2026, 1, 1), date(2026, 1, 2)) == (
        "date_mod=ge=2026-01-01;date_mod=le=2026-01-02 23:59:59"
    )


def test_changed_since_builds_an_open_ended_lower_bound() -> None:
    """Incremental sync needs a lower bound with no end."""

    assert changed_since(date(2026, 1, 1)) == "date_mod=ge=2026-01-01"


def test_changed_since_renders_a_datetime_to_the_second() -> None:
    """A datetime keeps its time component so a re-sync does not re-read a day."""

    moment = datetime(2026, 1, 1, 13, 45, 30)

    assert changed_since(moment) == "date_mod=ge=2026-01-01 13:45:30"


def test_changed_since_drops_the_offset_of_an_aware_datetime() -> None:
    """GLPI stores naive server-local timestamps and rejects an offset.

    An aware value is converted to UTC and rendered without the offset
    rather than being refused, so callers holding aware datetimes do not
    have to strip the tzinfo at every call site.
    """

    aware = datetime(2026, 1, 1, 13, 45, 30, tzinfo=timezone.utc)

    assert changed_since(aware) == "date_mod=ge=2026-01-01 13:45:30"


def test_changed_since_targets_any_field() -> None:
    """``field`` is overridable for columns other than ``date_mod``."""

    assert changed_since(date(2026, 1, 1), field="date_creation") == (
        "date_creation=ge=2026-01-01"
    )
