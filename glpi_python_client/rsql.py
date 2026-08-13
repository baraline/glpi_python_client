"""Public RSQL builders for GLPI v2 date filters.

GLPI v2 accepts RSQL expressions on the ``filter`` query parameter. Its
date grammar has two details that are easy to get subtly wrong and
impossible to notice when you do:

* the upper bound of a day-granular window has to be spelled through
  ``23:59:59``, because ``date_creation=le=2026-01-31`` compares against
  midnight and silently excludes everything that happened on the 31st;
* a filter field the server does not recognise is **ignored**, and the
  query then returns the whole unfiltered table rather than an error.
  A window built with a typo does not fail -- it succeeds, loudly and
  wrongly, with far too many rows;
* the column being compared holds **naive server-local** timestamps, so
  a bound built from an aware ``datetime`` has to be converted onto the
  server's clock before its offset is dropped. Rendering it in UTC
  instead shifts the bound by the server's offset -- harmless
  over-reading east of UTC, but four hours of missed modifications in
  New York and seven in Los Angeles, and a shift that changes at each
  DST boundary. Builders that take a time therefore take ``tz`` with it.

That second point is why these live on the public surface. Concatenating
the grammar at each call site means each call site is a fresh chance to
produce a filter that quietly matches everything.

This module is deliberately tree-neutral: it holds pure string logic with
no I/O, so unlike the internal composition helpers it is not duplicated
into the generated synchronous tree and can be imported from one place on
either surface.

Examples
--------
Counting one month of tickets::

    from glpi_python_client import created_between

    window = created_between("2026-01-01", "2026-01-31")
    tickets = await client.search_tickets(window)

Incremental sync since the last run::

    from glpi_python_client import changed_since

    window = changed_since(last_run, tz=client.server_timezone)
    async for batch in client.iter_search_tickets(window):
        ...
"""

from __future__ import annotations

from datetime import date, datetime, tzinfo

from glpi_python_client._errors import GlpiValidationError

#: Spelled-out end of day, appended to the upper bound of a date window.
#:
#: Without it GLPI compares against midnight and the final day of the
#: window is excluded -- a window that looks inclusive and is not.
_END_OF_DAY = "23:59:59"


def _coerce_date(value: date | str, *, parameter: str) -> date:
    """Return ``value`` as a :class:`datetime.date`.

    ``datetime`` is accepted and truncated, because a day-granular window
    built from ``datetime.now()`` is a normal thing to write.

    Raises
    ------
    GlpiValidationError
        When a string is not an ISO ``YYYY-MM-DD`` date. Failing here is
        the point: an unparsable value concatenated into a filter yields
        an expression GLPI ignores, and the query returns everything.
    """

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise GlpiValidationError(
            f"{parameter} must be a date or an ISO YYYY-MM-DD string; got {value!r}"
        ) from exc


def _render_moment(
    value: date | datetime | str,
    *,
    parameter: str,
    tz: tzinfo | None = None,
) -> str:
    """Render one date or datetime the way GLPI's date columns expect.

    An aware ``datetime`` is converted into ``tz`` and rendered without
    its offset -- the same trade the model serialiser makes on the way
    out, and for the same reason. The column this filter is compared
    against holds naive server-local timestamps, and GLPI does not accept
    an offset suffix on a filter, so an offset left in place produces an
    expression the server ignores and a query that returns everything.

    Two rules mirror the model layer:

    * **Naive values are left alone.** A naive datetime already means the
      server's clock; converting it would require guessing which zone the
      caller meant.
    * **No zone means no guess.** An aware value with no ``tz`` is
      refused rather than assumed to be UTC. Assuming is what
      ``server_timezone`` was made mandatory to stop: it shifts the bound
      by the server's offset, which merely re-reads a few hours east of
      UTC but skips modifications west of it, and the size of the shift
      changes at each DST boundary.

    Raises
    ------
    GlpiValidationError
        When ``value`` is an aware ``datetime`` and no ``tz`` is given,
        or when a string is not an ISO ``YYYY-MM-DD`` date.
    """

    if isinstance(value, datetime):
        moment = value
        if value.tzinfo is not None:
            if tz is None:
                raise GlpiValidationError(
                    f"{parameter} is timezone-aware, so rendering it needs the "
                    "GLPI server's timezone: pass tz=client.server_timezone. "
                    "GLPI compares this filter against a naive server-local "
                    "column, so guessing the zone would shift the bound by the "
                    "offset -- skipping modifications rather than failing."
                )
            moment = value.astimezone(tz).replace(tzinfo=None)
        return moment.strftime("%Y-%m-%d %H:%M:%S")
    return _coerce_date(value, parameter=parameter).isoformat()


def date_window(
    field: str,
    start: date | str,
    end: date | str,
) -> str:
    """Build an inclusive day-granular RSQL window on one date field.

    Parameters
    ----------
    field : str
        Name of the GLPI date column, e.g. ``"date_creation"``.
    start : date | str
        First day included, as a ``date`` or an ISO ``YYYY-MM-DD`` string.
    end : date | str
        Last day included. Rendered through ``23:59:59`` so the day itself
        is inside the window.

    Returns
    -------
    str
        An RSQL expression joining the two bounds with ``;`` (AND), ready
        to pass as ``rsql_filter``.

    Raises
    ------
    GlpiValidationError
        If either bound is unparsable, or ``start`` falls after ``end``.

    Examples
    --------
    >>> date_window("date_creation", "2026-01-01", "2026-01-31")
    'date_creation=ge=2026-01-01;date_creation=le=2026-01-31 23:59:59'
    """

    first = _coerce_date(start, parameter="start")
    last = _coerce_date(end, parameter="end")
    if first > last:
        raise GlpiValidationError(
            f"start ({first.isoformat()}) must not be after end ({last.isoformat()}); "
            "GLPI answers a contradictory window with zero rows rather than an error."
        )
    return f"{field}=ge={first.isoformat()};{field}=le={last.isoformat()} {_END_OF_DAY}"


def created_between(start: date | str, end: date | str) -> str:
    """Build an inclusive window on ``date_creation``.

    The common case, and the one every reporting helper in this package
    uses. See :func:`date_window` for the parameters.

    Examples
    --------
    >>> created_between("2026-01-01", "2026-01-31")
    'date_creation=ge=2026-01-01;date_creation=le=2026-01-31 23:59:59'
    """

    return date_window("date_creation", start, end)


def changed_since(
    moment: date | datetime | str,
    *,
    field: str = "date_mod",
    tz: tzinfo | None = None,
) -> str:
    """Build an open-ended lower bound on a date field.

    Intended for incremental sync: fetch what changed since the last run,
    with no upper bound.

    Parameters
    ----------
    moment : date | datetime | str
        Lower bound. A ``datetime`` keeps its time component so a re-sync
        does not re-read a whole day. A naive one is taken to be on the
        server's clock already; an aware one needs ``tz``.
    field : str, optional
        Date column to compare (defaults to ``"date_mod"``).
    tz : tzinfo, optional
        The GLPI server's timezone, used to render an aware ``moment`` on
        the server's clock before its offset is dropped. Pass
        ``client.server_timezone``, which the client has already resolved.
        Not needed for a ``date``, an ISO string, or a naive ``datetime``.

    Returns
    -------
    str
        An RSQL expression ready to pass as ``rsql_filter``.

    Raises
    ------
    GlpiValidationError
        If ``moment`` is a string that is not an ISO date, or is an aware
        ``datetime`` and ``tz`` was not supplied.

    Examples
    --------
    >>> changed_since("2026-01-01")
    'date_mod=ge=2026-01-01'

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> paris = ZoneInfo("Europe/Paris")
    >>> changed_since(datetime(2026, 8, 12, 9, 33, tzinfo=paris), tz=paris)
    'date_mod=ge=2026-08-12 09:33:00'
    """

    return f"{field}=ge={_render_moment(moment, parameter='moment', tz=tz)}"


__all__ = ["changed_since", "created_between", "date_window"]
