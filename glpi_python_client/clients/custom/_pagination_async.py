"""Asynchronous overrides for the three paginated search generators.

Each of the three ``iter_search_*`` generators in the API mixins
delegates its pagination loop to a ``self.search_*()`` call.  When the
:class:`~glpi_python_client.clients.commons._async_bridge.AsyncBridge`
wraps a sync generator it drives ``next()`` on the generator object inside
a worker thread.  Inside that thread ``self`` is still the
:class:`~glpi_python_client.clients.AsyncGlpiClient` instance, so
``self.search_tickets(...)`` resolves to the bridge-wrapped coroutine
function and calling it without ``await`` returns a coroutine object
instead of the expected list — triggering a
``RuntimeWarning: coroutine … was never awaited`` and a 500 response.

This mixin replaces all three generators with native async generators that
``await self.search_*(...)`` directly on the event loop.

The mixin must be positioned **before** ``TicketMixin``, ``UserMixin``, and
``EntityMixin`` in the :class:`~glpi_python_client.clients.AsyncGlpiClient`
base list so that the bridge's ``__init_subclass__`` hook finds the async
generator via ``getattr`` before it would otherwise wrap the sync version.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from glpi_python_client.models.api_schema.administration._entity import GetEntity
from glpi_python_client.models.api_schema.administration._user import GetUser
from glpi_python_client.models.api_schema.assistance._ticket import GetTicket


class AsyncPaginationMixin:
    """Async generator overrides for the three paginated search helpers.

    Each override re-implements the simple ``start``-advancing loop of
    the synchronous counterpart but ``await``\\ s the underlying
    ``search_*`` call so it runs on the event loop rather than inside a
    worker-thread-dispatched ``next()`` call where the coroutine would
    be dropped on the floor.
    """

    async def iter_search_tickets(
        self,
        rsql_filter: str = "",
        *,
        batch_size: int = 50,
        sort: str | None = None,
        fields: tuple[str, ...] = (),
    ) -> AsyncIterator[list[GetTicket]]:
        """Yield successive pages of GLPI tickets until exhausted.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
            Empty by default, which lists every visible ticket.
        batch_size : int, optional
            Number of records requested per page (default 50).
        sort : str | None, optional
            ``sort`` query parameter forwarded as-is to each page request.
        fields : tuple[str, ...], optional
            Restricted set of contract field names to request.

        Yields
        ------
        list[GetTicket]
            One page of tickets per iteration. The last yielded batch may
            be shorter than ``batch_size``.
        """

        start = 0
        while True:
            batch: list[GetTicket] = await self.search_tickets(  # type: ignore[attr-defined]
                rsql_filter,
                limit=batch_size,
                start=start,
                sort=sort,
                fields=fields,
            )
            if batch:
                yield batch
            if len(batch) < batch_size:
                break
            start += batch_size

    async def iter_search_users(
        self,
        rsql_filter: str = "",
        *,
        batch_size: int = 50,
        skip_entity: bool = False,
    ) -> AsyncIterator[list[GetUser]]:
        """Yield successive pages of GLPI users until exhausted.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
            Empty by default, which lists every visible user.
        batch_size : int, optional
            Number of records requested per page (default 50).
        skip_entity : bool, optional
            When ``True`` the ``GLPI-Entity`` header is omitted so the
            search spans every entity the caller has access to.

        Yields
        ------
        list[GetUser]
            One page of users per iteration. The last yielded batch may
            be shorter than ``batch_size``.
        """

        start = 0
        while True:
            batch: list[GetUser] = await self.search_users(  # type: ignore[attr-defined]
                rsql_filter,
                limit=batch_size,
                start=start,
                skip_entity=skip_entity,
            )
            if batch:
                yield batch
            if len(batch) < batch_size:
                break
            start += batch_size

    async def iter_search_entities(
        self,
        rsql_filter: str = "",
        *,
        batch_size: int = 50,
    ) -> AsyncIterator[list[GetEntity]]:
        """Yield successive pages of GLPI entities until exhausted.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
            Empty by default, which lists every accessible entity.
        batch_size : int, optional
            Number of records requested per page (default 50).

        Yields
        ------
        list[GetEntity]
            One page of entities per iteration. The last yielded batch
            may be shorter than ``batch_size``.
        """

        start = 0
        while True:
            batch: list[GetEntity] = await self.search_entities(  # type: ignore[attr-defined]
                rsql_filter,
                limit=batch_size,
                start=start,
            )
            if batch:
                yield batch
            if len(batch) < batch_size:
                break
            start += batch_size


__all__ = ["AsyncPaginationMixin"]
