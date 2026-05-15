"""Asynchronous task search operations for GLPI v2 clients.

This module contains the global async task search helper used by the
asynchronous high-level client.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any, cast, overload

from glpi_python_client.clients.v2.common.constants import (
    TASK_SEARCH_ENDPOINTS,
)
from glpi_python_client.clients.v2.common.task_search import (
    build_task_search_params,
    merge_list_task_fields,
)
from glpi_python_client.clients.v2.common.ticket_search import (
    advance_ticket_search_pagination,
)
from glpi_python_client.content.records.parsers.timeline import _glpi_task_record
from glpi_python_client.models import GlpiTask

from .transport import AsyncTransportMixin

logger = logging.getLogger(__name__)


class AsyncTaskMixin(AsyncTransportMixin):
    """Asynchronous GLPI task search helpers.

    The mixin exposes the async counterpart of ``search_task_records`` while
    sharing the same field merging and endpoint fallback rules as sync code.
    """

    @overload
    async def search_task_records(
        self,
        query: str | None = None,
        *,
        fields: tuple[str, ...] = (),
        sort: str | None = None,
        batch_size: None = None,
    ) -> list[GlpiTask]: ...

    @overload
    async def search_task_records(
        self,
        query: str | None = None,
        *,
        fields: tuple[str, ...] = (),
        sort: str | None = None,
        batch_size: int,
    ) -> AsyncIterator[list[GlpiTask]]: ...

    async def search_task_records(
        self,
        query: str | None = None,
        *,
        fields: tuple[str, ...] = (),
        sort: str | None = None,
        batch_size: int | None = None,
    ) -> list[GlpiTask] | AsyncIterator[list[GlpiTask]]:
        """Search GLPI task records and return either a full list or batches.

        Passing ``batch_size`` switches the method into streaming mode and
        returns an async iterator of typed task batches instead of one
        materialized list.
        """

        if batch_size is not None and batch_size < 1:
            raise ValueError("batch_size must be a positive integer or None")

        merged_fields = merge_list_task_fields(list(fields) or None)
        batches = self._iter_task_record_batches(
            query=query,
            fields=merged_fields,
            sort=sort,
            batch_size=batch_size,
        )
        if batch_size is not None:
            return batches

        records: list[GlpiTask] = []
        async for page in batches:
            records.extend(page)
        return records

    async def _iter_task_record_batches(
        self,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        sort: str | None = None,
        batch_size: int | None = None,
    ) -> AsyncIterator[list[GlpiTask]]:
        """Yield typed task batches produced from paginated raw payloads.

        Each yielded batch already contains parsed ``GlpiTask`` objects.
        """

        async for page in self._yield_task_payloads(
            query=query,
            fields=fields,
            sort=sort,
            batch_size=batch_size,
        ):
            yield [
                _glpi_task_record(raw_task)
                for raw_task in page
                if isinstance(raw_task, dict)
            ]

    async def _yield_task_payloads(
        self,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        sort: str | None = None,
        batch_size: int | None = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Yield paginated raw task payload batches from the GLPI API.

        The first request discovers the supported task collection endpoint and
        subsequent pages keep using that same endpoint.
        """

        params = build_task_search_params(
            query=query,
            fields=fields,
            sort=sort,
            batch_size=batch_size,
        )

        endpoint: str | None = None
        observed_page_size = batch_size
        while True:
            current_start = cast(int, params["start"])
            response = None
            if endpoint is None:
                for candidate in TASK_SEARCH_ENDPOINTS:
                    response = await self._get_request(candidate, params)
                    if response.status_code in (200, 206):
                        endpoint = candidate
                        break
                if response is None or endpoint is None:
                    return
            else:
                response = await self._get_request(endpoint, params)

            if response.status_code not in (200, 206):
                logger.info(
                    "GLPI task search returned status %s (start=%d)",
                    response.status_code,
                    current_start,
                )
                return

            batch = response.json()
            if not isinstance(batch, list) or not batch:
                logger.info(
                    "GLPI task search returned empty batch (start=%d)",
                    current_start,
                )
                return

            logger.info(
                "GLPI task search: batch of %d tasks (start=%d endpoint=%s)",
                len(batch),
                current_start,
                endpoint,
            )
            yield [dict(task) for task in batch if isinstance(task, dict)]

            next_start, observed_page_size, should_continue = (
                advance_ticket_search_pagination(
                    current_start=current_start,
                    page_size=len(batch),
                    content_range=response.headers.get("Content-Range", ""),
                    observed_page_size=observed_page_size,
                )
            )
            params["start"] = next_start
            if not should_continue:
                return
