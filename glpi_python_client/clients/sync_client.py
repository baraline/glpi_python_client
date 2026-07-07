"""Public synchronous GLPI client class.

The :class:`GlpiClient` class composes the per-endpoint mixins from
:mod:`glpi_python_client.clients.api` with the custom helpers from
:mod:`glpi_python_client.clients.custom` and the synchronous transport
mixin from :mod:`glpi_python_client.clients.commons` to expose the full
public client surface.

The asynchronous counterpart
:class:`~glpi_python_client.clients.async_client.AsyncGlpiClient` wraps
this very same set of mixins through
:class:`~glpi_python_client.clients.commons._async_bridge.AsyncBridge` so
both surfaces stay in lock-step automatically.
"""

from __future__ import annotations

import logging
import sys
from types import TracebackType

if sys.version_info >= (3, 11):
    from typing import Self
else:  # pragma: no cover - fallback for Python 3.10
    from typing_extensions import Self

from glpi_python_client.clients._base_client import _BaseGlpiClient
from glpi_python_client.clients.api import (
    DocumentMixin,
    EntityMixin,
    FollowupMixin,
    KBArticleMixin,
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
from glpi_python_client.clients.commons._transport import TransportMixin
from glpi_python_client.clients.custom import (
    StatisticsMixin,
    TicketContextMixin,
)

logger = logging.getLogger(__name__)


class GlpiClient(
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
    KBArticleMixin,
    PluginFieldsMixin,
    TicketContextMixin,
    StatisticsMixin,
    _BaseGlpiClient,
    TransportMixin,
):
    """Synchronous GLPI client backed by the contract-aligned API mixins.

    The client owns the shared HTTP session, OAuth token manager, and
    optional legacy v1 session used solely for binary document uploads.
    Token acquisition is serialised by a :class:`threading.Lock` so the
    same instance can be safely shared across threads as well as across
    asyncio tasks dispatched through
    :class:`~glpi_python_client.clients.async_client.AsyncGlpiClient`.

    Construction parameters and :meth:`from_env` are documented on
    :class:`~glpi_python_client.clients._base_client._BaseGlpiClient`.
    """

    def close(self) -> None:
        """Release every resource owned by the client.

        The shared HTTP session is closed, the optional v1 fallback
        session is closed, and the client is marked as closed so
        subsequent calls raise immediately. The method is idempotent.
        """

        if self._closed:
            return
        try:
            self._session.close()
            if self._v1 is not None:
                self._v1.close()
        finally:
            self._closed = True

    def __enter__(self) -> Self:
        """Return the client unchanged for use in a ``with`` block.

        Returns
        -------
        GlpiClient
            The client itself, suitable for chaining method calls.
        """

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the client on ``with`` exit.

        Parameters
        ----------
        exc_type : type[BaseException] | None
            Exception class raised inside the ``with`` block, if any.
        exc : BaseException | None
            Exception instance raised inside the block, if any.
        tb : TracebackType | None
            Traceback associated with ``exc``.
        """

        self.close()


__all__ = ["GlpiClient"]
