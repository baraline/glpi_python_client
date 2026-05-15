"""Task search field and pagination helpers for GLPI v2 clients.

These helpers keep field merging and pagination math aligned between the sync
and async task-search implementations.
"""

from __future__ import annotations

from .constants import LIST_TASK_CORE_FIELDS


def merge_list_task_fields(fields: list[str] | None) -> list[str] | None:
    """Merge caller-requested task fields with required core task fields.

    The helper preserves caller order while ensuring the fields needed for task
    parsing remain present even when the caller requests a narrow field list.
    """

    if fields is None:
        return list(LIST_TASK_CORE_FIELDS)
    return list(dict.fromkeys([*fields, *LIST_TASK_CORE_FIELDS]))


def build_task_search_params(
    *,
    query: str | None = None,
    fields: list[str] | None = None,
    sort: str | None = None,
    batch_size: int | None = None,
) -> dict[str, object]:
    """Build the request parameter mapping for a task search call.

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
