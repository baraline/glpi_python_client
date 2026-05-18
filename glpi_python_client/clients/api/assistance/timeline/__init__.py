"""GLPI ticket-timeline mixins for the Synchronous client."""

from __future__ import annotations

from glpi_python_client.clients.api.assistance.timeline._document import (
    TimelineDocumentMixin,
)
from glpi_python_client.clients.api.assistance.timeline._followup import (
    FollowupMixin,
)
from glpi_python_client.clients.api.assistance.timeline._solution import (
    SolutionMixin,
)
from glpi_python_client.clients.api.assistance.timeline._task import (
    TicketTaskMixin,
)

__all__ = [
    "FollowupMixin",
    "SolutionMixin",
    "TicketTaskMixin",
    "TimelineDocumentMixin",
]
