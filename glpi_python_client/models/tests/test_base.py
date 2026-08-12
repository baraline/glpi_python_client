"""Unit tests for :mod:`glpi_python_client.models._base`.

The timezone tests here pin the inbound half of the server-timezone
contract: GLPI sends most timestamps with an offset but not all of them,
and a payload carrying both kinds is what makes a plain comparison raise.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from glpi_python_client.models._base import GlpiModel

_PARIS_SUMMER = timezone(timedelta(hours=2))


class _Stamped(GlpiModel):
    """Model with one optional datetime field, used by the tests below."""

    id: int | None = None
    date: datetime | None = None


class _Nested(GlpiModel):
    """Model holding a submodel, to prove the context reaches nested values."""

    id: int | None = None
    inner: _Stamped | None = None


def test_naive_datetime_gains_the_server_timezone() -> None:
    """A timestamp sent without an offset is stamped with the server's."""

    parsed = _Stamped.model_validate(
        {"id": 1, "date": "2018-04-06 17:39:44"},
        context={"server_timezone": _PARIS_SUMMER},
    )

    assert parsed.date is not None
    assert parsed.date.utcoffset() == timedelta(hours=2)
    assert parsed.date.isoformat() == "2018-04-06T17:39:44+02:00"


def test_aware_datetime_keeps_the_offset_the_server_sent() -> None:
    """An offset already on the wire wins over the configured timezone.

    GLPI sends the correct historical offset -- the same instance emits
    ``+02:00`` in summer and ``+01:00`` in winter -- so overwriting it with
    a single configured zone would corrupt half the year.
    """

    parsed = _Stamped.model_validate(
        {"id": 1, "date": "2019-01-15T09:00:00+01:00"},
        context={"server_timezone": _PARIS_SUMMER},
    )

    assert parsed.date is not None
    assert parsed.date.utcoffset() == timedelta(hours=1)


def test_naive_datetime_stays_naive_without_a_context() -> None:
    """No configured timezone means no guess.

    Stamping an arbitrary offset on an unknown value would turn a loud
    ``TypeError`` on comparison into a silently wrong result, so a model
    validated outside the client keeps what it was given.
    """

    parsed = _Stamped.model_validate({"id": 1, "date": "2018-04-06 17:39:44"})

    assert parsed.date is not None
    assert parsed.date.tzinfo is None


def test_the_timezone_reaches_a_nested_model() -> None:
    """Submodels are stamped too, which is where the naive values live.

    The one field GLPI 11 sends naive is ``KBArticle.revisions[].date`` --
    nested inside an article whose own timestamps are aware.
    """

    parsed = _Nested.model_validate(
        {"id": 1, "inner": {"id": 2, "date": "2018-04-06 17:39:44"}},
        context={"server_timezone": _PARIS_SUMMER},
    )

    assert parsed.inner is not None
    assert parsed.inner.date is not None
    assert parsed.inner.date.utcoffset() == timedelta(hours=2)


def test_none_datetime_is_left_alone() -> None:
    """An absent timestamp stays absent rather than becoming an epoch."""

    parsed = _Stamped.model_validate(
        {"id": 1}, context={"server_timezone": _PARIS_SUMMER}
    )

    assert parsed.date is None


def test_non_datetime_fields_are_untouched() -> None:
    """Only datetime fields are considered; the rest pass through."""

    parsed = _Stamped.model_validate(
        {"id": 7, "date": None}, context={"server_timezone": _PARIS_SUMMER}
    )

    assert parsed.id == 7


def test_validating_an_existing_instance_does_not_mutate_the_original() -> None:
    """Re-validation returns a stamped copy and leaves the caller's object.

    A ``mode="after"`` validator receives the model itself, so assigning to
    it in place would reach back into an object the caller still holds.
    """

    original = _Stamped(id=1, date=datetime(2018, 4, 6, 17, 39, 44))

    revalidated = _Stamped.model_validate(
        original, context={"server_timezone": _PARIS_SUMMER}
    )

    assert revalidated.date is not None
    assert revalidated.date.utcoffset() == timedelta(hours=2)
    assert original.date is not None
    assert original.date.tzinfo is None
