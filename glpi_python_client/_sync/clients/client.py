"""Public GLPI client class.

Composes the per-endpoint mixins from
:mod:`glpi_python_client._sync.clients.api` with the aggregated helpers
from :mod:`glpi_python_client._sync.clients.custom` and the transport
mixin from :mod:`glpi_python_client._sync.clients.commons` to expose the
full public client surface.

This module is written once. Its counterpart on the other surface is
generated from it, so the two client classes cannot drift apart: there is
no second definition to keep in step.
"""

from __future__ import annotations

import logging
import sys
from types import TracebackType

if sys.version_info >= (3, 11):
    from typing import Self
else:  # pragma: no cover - fallback for Python 3.10
    from typing_extensions import Self

from glpi_python_client._sync.clients._base_client import _BaseGlpiClient
from glpi_python_client._sync.clients.api import (
    DocumentMixin,
    EntityMixin,
    FollowupMixin,
    KBArticleCommentMixin,
    KBArticleMixin,
    KBArticleRevisionMixin,
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
from glpi_python_client._sync.clients.commons._transport import TransportMixin
from glpi_python_client._sync.clients.custom import (
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
    KBArticleCommentMixin,
    KBArticleRevisionMixin,
    PluginFieldsMixin,
    TicketContextMixin,
    StatisticsMixin,
    _BaseGlpiClient,
    TransportMixin,
):
    """GLPI client backed by the contract-aligned API mixins.

    The client owns the shared HTTP session, the OAuth token manager, and
    the optional legacy v1 session used for binary document uploads and
    the Fields plugin endpoints. Token acquisition is serialised by the
    lock from :mod:`glpi_python_client._sync._concurrency`, which is the
    right primitive for this surface -- see that module for why the two
    surfaces cannot share one.

    Construction parameters and :meth:`from_env` are documented on
    :class:`~glpi_python_client._sync.clients._base_client._BaseGlpiClient`.
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
        AsyncGlpiClient
            The client itself, suitable for chaining method calls.
        """

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the client on ``with`` block exit.

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
