"""Synchronous GLPI v2 API mixin assembly.

This module combines the scope-focused synchronous mixins into the single API
surface consumed by the public ``GlpiClient`` class.
"""

from __future__ import annotations

from .analytics import SyncAnalyticsMixin
from .directory import SyncDirectoryMixin
from .documents import SyncDocumentMixin
from .tasks import SyncTaskMixin
from .team import SyncTeamMixin
from .tickets import SyncTicketMixin
from .timeline import SyncTimelineMixin
from .transport import SyncTransportMixin


class GlpiApiClientMixin(
    SyncAnalyticsMixin,
    SyncTicketMixin,
    SyncTimelineMixin,
    SyncTaskMixin,
    SyncDocumentMixin,
    SyncTeamMixin,
    SyncDirectoryMixin,
    SyncTransportMixin,
):
    """Combined synchronous GLPI v2 client behavior.

    The mixin class has no state of its own. It exists to provide a readable
    composition point for the synchronous endpoint and transport helpers.
    """
