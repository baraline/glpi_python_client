"""Unit tests for the public RSQL date builders."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

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


def test_changed_since_renders_an_aware_datetime_on_the_server_clock() -> None:
    """A Paris moment filtered against a Paris server keeps its wall time.

    This is the whole point of ``tz``. The column being compared holds
    naive server-local timestamps, so the bound has to name the same
    clock: 09:33 in Paris is the row's 09:33, not the 07:33 that
    converting to UTC would ask for.
    """

    aware = datetime(2026, 8, 12, 9, 33, tzinfo=ZoneInfo("Europe/Paris"))

    assert changed_since(aware, tz=ZoneInfo("Europe/Paris")) == (
        "date_mod=ge=2026-08-12 09:33:00"
    )


def test_changed_since_converts_an_aware_datetime_into_the_server_zone() -> None:
    """The offset is spent on the conversion, not discarded with the value.

    A caller holding UTC is the common case, and the bound it produces
    must be the server's rendering of that same instant.
    """

    aware = datetime(2026, 8, 12, 7, 33, tzinfo=timezone.utc)

    assert changed_since(aware, tz=ZoneInfo("Europe/Paris")) == (
        "date_mod=ge=2026-08-12 09:33:00"
    )


def test_changed_since_follows_dst_in_the_server_zone() -> None:
    """The same UTC wall time lands an hour apart across the DST boundary.

    A fixed offset would render these identically and be wrong for half
    the year, which is why ``tz`` is a zone rather than a delta.
    """

    paris = ZoneInfo("Europe/Paris")
    winter = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    summer = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)

    assert changed_since(winter, tz=paris) == "date_mod=ge=2026-01-15 13:00:00"
    assert changed_since(summer, tz=paris) == "date_mod=ge=2026-07-15 14:00:00"


def test_changed_since_rejects_an_aware_datetime_without_a_zone() -> None:
    """Without ``tz`` there is no clock to render the bound on.

    This replaces the behaviour where an aware value was assumed to mean
    UTC. That assumption was the same guess ``server_timezone`` was made
    mandatory to stop: it silently shifts the bound by the offset, which
    over-reads east of UTC and skips modifications west of it.
    """

    aware = datetime(2026, 1, 1, 13, 45, 30, tzinfo=timezone.utc)

    with pytest.raises(GlpiValidationError):
        changed_since(aware)


def test_changed_since_leaves_a_naive_datetime_alone() -> None:
    """A naive value already means the server's clock, ``tz`` or not.

    Converting it would require guessing which zone the caller meant --
    the inbound half of the package makes the same choice.
    """

    naive = datetime(2026, 1, 1, 13, 45, 30)

    assert changed_since(naive, tz=ZoneInfo("America/New_York")) == (
        "date_mod=ge=2026-01-01 13:45:30"
    )


def test_changed_since_ignores_the_zone_for_a_day_granular_bound() -> None:
    """A ``date`` carries no time to convert, so ``tz`` cannot move it."""

    assert changed_since(date(2026, 1, 1), tz=ZoneInfo("America/New_York")) == (
        "date_mod=ge=2026-01-01"
    )


def test_changed_since_targets_any_field() -> None:
    """``field`` is overridable for columns other than ``date_mod``."""

    assert changed_since(date(2026, 1, 1), field="date_creation") == (
        "date_creation=ge=2026-01-01"
    )
