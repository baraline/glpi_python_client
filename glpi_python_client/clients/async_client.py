"""Public asynchronous GLPI client class.

The :class:`AsyncGlpiClient` reuses every synchronous mixin composed
into :class:`~glpi_python_client.clients.sync_client.GlpiClient` and
wraps each public method into a coroutine through
:class:`~glpi_python_client.clients.commons._async_bridge.AsyncBridge`.
Helpers that benefit from concurrent fan-out
(:meth:`get_ticket_context`, :meth:`get_task_statistics`) are replaced
by their dedicated async overrides under
:mod:`glpi_python_client.clients.custom`.

The async client owns the same HTTP session and token manager as the
synchronous client but its lifecycle is driven through ``async with`` /
``await close()``. Token acquisition is still serialised by the shared
:class:`threading.Lock` so concurrent ``asyncio.gather`` calls cannot
race on the worker threads spawned by :func:`asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from concurrent.futures import Executor
from types import TracebackType
from typing import Any

if sys.version_info >= (3, 11):
    from typing import Self
else:  # pragma: no cover - fallback for Python 3.10
    from typing_extensions import Self

from glpi_python_client.clients._base_client import _BaseGlpiClient
from glpi_python_client.clients.api import (
    DocumentMixin,
    EntityMixin,
    FollowupMixin,
    KBCategoryMixin,
    LocationMixin,
    PluginFieldsMixin,
    SolutionMixin,
    TeamMemberMixin,
    TicketMixin,
    TicketTaskMixin,
    TimelineDocumentMixin,
    UserMixin,
)
from glpi_python_client.clients.commons._async_bridge import AsyncBridge
from glpi_python_client.clients.commons._transport import TransportMixin
from glpi_python_client.clients.custom._pagination_async import AsyncPaginationMixin
from glpi_python_client.clients.custom._statistics_async import AsyncStatisticsMixin
from glpi_python_client.clients.custom._ticket_context_async import (
    AsyncTicketContextMixin,
)

logger = logging.getLogger(__name__)


class AsyncGlpiClient(  # type: ignore[misc]
    AsyncBridge,
    AsyncPaginationMixin,
    TicketMixin,
    TicketTaskMixin,
    FollowupMixin,
    SolutionMixin,
    TimelineDocumentMixin,
    TeamMemberMixin,
    DocumentMixin,
    UserMixin,
    EntityMixin,
    LocationMixin,
    KBCategoryMixin,
    PluginFieldsMixin,
    AsyncTicketContextMixin,
    AsyncStatisticsMixin,
    _BaseGlpiClient,
    TransportMixin,
):
    """Asynchronous GLPI client built on the sync mixins via the bridge.

    Every public sync method exposed by the inherited mixins is
    automatically wrapped into a coroutine that defers the blocking call
    to a worker thread. The custom helpers that benefit from concurrent
    fan-out provide hand-written async overrides which are preserved as
    coroutine functions by the bridge.

    Construction parameters and :meth:`from_env` are documented on
    :class:`~glpi_python_client.clients._base_client._BaseGlpiClient`;
    the only additional keyword is ``executor`` (described below).
    """

    def __init__(self, *, executor: Executor | None = None, **kwargs: Any) -> None:
        """Build an asynchronous GLPI client and its transport resources.

        Parameters
        ----------
        executor : concurrent.futures.Executor | None, optional
            Optional executor every wrapped call is routed through. When
            ``None`` (the default) the bridge falls back to
            :func:`asyncio.to_thread`, which uses the loop's default
            thread pool executor. Supply a dedicated
            :class:`concurrent.futures.ThreadPoolExecutor` when the
            application performs aggressive fan-outs that would
            otherwise saturate the default pool.
        **kwargs : Any
            Remaining keyword arguments forwarded to
            :class:`~glpi_python_client.clients._base_client._BaseGlpiClient`.

        Raises
        ------
        ValueError
            If the supplied configuration is incomplete or invalid (e.g.
            missing OAuth credentials together with no v1 fallback).
        """

        super().__init__(**kwargs)
        self._executor = executor

    async def close(self) -> None:
        """Release every resource owned by the client.

        The shared HTTP session is closed off-thread, the optional v1
        fallback session is closed off-thread, and the client is marked
        as closed so subsequent calls raise immediately. The method is
        idempotent.
        """

        if self._closed:
            return
        try:
            await asyncio.to_thread(self._session.close)
            if self._v1 is not None:
                await asyncio.to_thread(self._v1.close)
        finally:
            self._closed = True

    async def __aenter__(self) -> Self:
        """Return the client unchanged for use in an ``async with`` block.

        Returns
        -------
        AsyncGlpiClient
            The client itself, suitable for chaining method calls.
        """

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the client on ``async with`` exit.

        Parameters
        ----------
        exc_type : type[BaseException] | None
            Exception class raised inside the ``async with`` block, if any.
        exc : BaseException | None
            Exception instance raised inside the block, if any.
        tb : TracebackType | None
            Traceback associated with ``exc``.
        """

        await self.close()


__all__ = ["AsyncGlpiClient"]
