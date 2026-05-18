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
import os
import sys
import threading
from concurrent.futures import Executor
from types import TracebackType
from typing import TYPE_CHECKING

if sys.version_info >= (3, 11):
    from typing import Self
else:  # pragma: no cover - fallback for Python 3.10
    from typing_extensions import Self

from glpi_python_client.clients.api import (
    DocumentMixin,
    EntityMixin,
    FollowupMixin,
    LocationMixin,
    SolutionMixin,
    TeamMemberMixin,
    TicketMixin,
    TicketTaskMixin,
    TimelineDocumentMixin,
    UserMixin,
)
from glpi_python_client.clients.commons._async_bridge import AsyncBridge
from glpi_python_client.clients.commons._config import (
    build_client_env_config,
    build_client_resources,
)
from glpi_python_client.clients.commons._transport import TransportMixin
from glpi_python_client.clients.custom._pagination_async import AsyncPaginationMixin
from glpi_python_client.clients.custom._statistics_async import AsyncStatisticsMixin
from glpi_python_client.clients.custom._ticket_context_async import (
    AsyncTicketContextMixin,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

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
    AsyncTicketContextMixin,
    AsyncStatisticsMixin,
    TransportMixin,
):
    """Asynchronous GLPI client built on the sync mixins via the bridge.

    Every public sync method exposed by the inherited mixins is
    automatically wrapped into a coroutine that defers the blocking call
    to a worker thread. The custom helpers that benefit from concurrent
    fan-out provide hand-written async overrides which are preserved as
    coroutine functions by the bridge.
    """

    def __init__(
        self,
        *,
        glpi_api_url: str,
        client_id: str | None = None,
        client_secret: str | None = None,
        username: str | None = None,
        password: str | None = None,
        glpi_entity: int | None = None,
        glpi_profile: int | None = None,
        entity_recursive: bool = False,
        language: str = "en_GB",
        verify_ssl: bool = True,
        auth_token_refresh: int | None = None,
        v1_base_url: str | None = None,
        v1_user_token: str | None = None,
        v1_app_token: str | None = None,
        executor: Executor | None = None,
    ) -> None:
        """Build an asynchronous GLPI client and its transport resources.

        Parameters mirror :class:`GlpiClient` with one extra option:

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

        Raises
        ------
        ValueError
            If the supplied configuration is incomplete or invalid (e.g.
            missing OAuth credentials together with no v1 fallback).
        """

        resources = build_client_resources(
            glpi_api_url=glpi_api_url,
            client_name=type(self).__name__,
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            verify_ssl=verify_ssl,
            auth_token_refresh=auth_token_refresh,
            v1_base_url=v1_base_url,
            v1_user_token=v1_user_token,
            v1_app_token=v1_app_token,
        )
        self.glpi_api_url = resources.glpi_api_url
        self._session = resources.session
        self._auth = resources.auth
        self._v1 = resources.v1
        self.glpi_entity = glpi_entity
        self.glpi_profile = glpi_profile
        self.entity_recursive = entity_recursive
        self.language = language
        self._auth_lock = threading.Lock()
        self._closed = False
        self._executor = executor

    @classmethod
    def from_env(
        cls,
        *,
        env: Mapping[str, str] | None = None,
        prefix: str = "GLPI_",
        executor: Executor | None = None,
        **overrides: object,
    ) -> Self:
        """Build a client instance from environment variables.

        Parameters
        ----------
        env : Mapping[str, str] | None, optional
            Mapping the helper reads values from. Defaults to
            :data:`os.environ`.
        prefix : str, optional
            Common prefix shared by every environment variable name.
        executor : concurrent.futures.Executor | None, optional
            Optional executor forwarded to the constructor.
        **overrides : object
            Keyword overrides forwarded to :meth:`__init__`.

        Returns
        -------
        AsyncGlpiClient
            A fully configured async client ready to perform requests.
        """

        config = build_client_env_config(
            prefix=prefix,
            env=env if env is not None else os.environ,
            overrides=overrides,
        )
        return cls(executor=executor, **config)  # type: ignore[arg-type]

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
