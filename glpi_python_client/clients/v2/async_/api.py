"""Asynchronous GLPI v2 API mixin assembly.

This module combines the scope-focused async mixins into the single API surface
consumed by the public ``AsyncGlpiClient`` class.
"""

from __future__ import annotations

from .analytics import AsyncAnalyticsMixin
from .directory import AsyncDirectoryMixin
from .documents import AsyncDocumentMixin
from .tasks import AsyncTaskMixin
from .team import AsyncTeamMixin
from .tickets import AsyncTicketMixin
from .timeline import AsyncTimelineMixin
from .transport import AsyncTransportMixin


class AsyncGlpiApiClientMixin(
    AsyncAnalyticsMixin,
    AsyncTicketMixin,
    AsyncTimelineMixin,
    AsyncTaskMixin,
    AsyncDocumentMixin,
    AsyncTeamMixin,
    AsyncDirectoryMixin,
    AsyncTransportMixin,
):
    """Combined asynchronous GLPI v2 client behavior.

    The mixin class exists as the composition point for the async endpoint and
    transport helpers used by ``AsyncGlpiClient``.
    """
