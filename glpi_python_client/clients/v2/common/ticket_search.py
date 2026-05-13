"""Ticket search field and pagination helpers for GLPI v2 clients.

These helpers keep field merging, deleted-ticket filtering, and pagination math
in one place so sync and async search implementations behave the same way.
"""

from __future__ import annotations

from typing import Any

from glpi_python_client.content.records.parsers.tickets import (
    _filter_visible_ticket_batch,
)

from .constants import LIST_TICKET_CORE_FIELDS


def merge_list_ticket_fields(fields: list[str] | None) -> list[str] | None:
    """Merge caller-requested list fields with required core ticket fields.

    The helper preserves caller order while ensuring the fields needed for the
    package's ticket parsing logic are always present.
    """

    if fields is None:
        return list(LIST_TICKET_CORE_FIELDS)
    return list(dict.fromkeys([*fields, *LIST_TICKET_CORE_FIELDS]))


def is_deleted_ticket(record: dict[str, Any]) -> bool:
    """Return whether one raw GLPI ticket payload represents a deleted ticket.

    This delegates to the shared batch filter so the single-record check uses
    the exact same deleted-ticket rules as paginated search results.
    """

    return _filter_visible_ticket_batch([record])[1] == 1


def build_ticket_search_params(
    *,
    query: str | None = None,
    fields: list[str] | None = None,
    sort: str | None = None,
    batch_size: int | None = None,
) -> dict[str, object]:
    """Build the request parameter mapping for a ticket search call.

    Search pagination always starts at zero here, and optional query, field,
    sort, and limit arguments are included only when the caller supplies them.
    """

    params: dict[str, object] = {"start": 0}
    if batch_size is not None:
        params["limit"] = batch_size
    if query:
        params["filter"] = query
    if fields:
        params["fields"] = ",".join(fields)
    if sort:
        params["sort"] = sort
    return params


def filter_ticket_search_batch(
    batch: list[object],
    *,
    include_deleted_ticket: bool,
) -> tuple[list[dict[str, Any]], int]:
    """Return visible ticket payloads and the number excluded as deleted.

    When deleted tickets are allowed, the helper simply normalizes dictionary
    items. Otherwise it defers to the shared deleted-ticket filter.
    """

    if include_deleted_ticket:
        return [dict(ticket) for ticket in batch if isinstance(ticket, dict)], 0
    return _filter_visible_ticket_batch(batch)


def advance_ticket_search_pagination(
    *,
    current_start: int,
    page_size: int,
    content_range: str,
    observed_page_size: int | None,
) -> tuple[int, int | None, bool]:
    """Return the next ticket page start and whether another page is needed.

    The function prefers the server-provided ``Content-Range`` total when it is
    available and otherwise falls back to observed page sizes to decide whether
    iteration should continue.
    """

    total_count: int | None = None
    if content_range:
        try:
            total_count = int(content_range.split("/")[-1])
        except (ValueError, IndexError):
            total_count = None

    next_start = current_start + page_size
    if total_count is not None:
        return next_start, observed_page_size, next_start < total_count

    next_observed_page_size = observed_page_size
    if next_observed_page_size is None:
        next_observed_page_size = page_size
    return (
        next_start,
        next_observed_page_size,
        page_size >= next_observed_page_size,
    )
