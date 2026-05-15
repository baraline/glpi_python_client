"""Timeline sub-resource schemas for ticket-attached records.

These models cover the GLPI timeline endpoints exposed under
``/Assistance/Ticket/{id}/Timeline/{Followup,Task,Solution,Document}``.
"""

from glpi_python_client.models.api_schema.assistance.timeline._document import (
    DeleteTimelineDocument,
    GetTimelineDocument,
    PatchTimelineDocument,
    PostTimelineDocument,
)
from glpi_python_client.models.api_schema.assistance.timeline._followup import (
    DeleteFollowup,
    GetFollowup,
    PatchFollowup,
    PostFollowup,
)
from glpi_python_client.models.api_schema.assistance.timeline._solution import (
    DeleteSolution,
    GetSolution,
    PatchSolution,
    PostSolution,
)
from glpi_python_client.models.api_schema.assistance.timeline._task import (
    DeleteTicketTask,
    GetTicketTask,
    PatchTicketTask,
    PostTicketTask,
)

__all__ = [
    "DeleteFollowup",
    "DeleteSolution",
    "DeleteTicketTask",
    "DeleteTimelineDocument",
    "GetFollowup",
    "GetSolution",
    "GetTicketTask",
    "GetTimelineDocument",
    "PatchFollowup",
    "PatchSolution",
    "PatchTicketTask",
    "PatchTimelineDocument",
    "PostFollowup",
    "PostSolution",
    "PostTicketTask",
    "PostTimelineDocument",
]
