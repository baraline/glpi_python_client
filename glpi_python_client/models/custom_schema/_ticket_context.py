"""Aggregated ticket context view bundling timeline records.

The ticket context model gathers the primary ticket record together with
the most common timeline records (followups, tasks, solutions) and any
linked documents. It is consumed by higher-level workflows that need a
single object to reason about a ticket and its history.
"""

from __future__ import annotations

from pydantic import Field

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema.assistance._ticket import GetTicket
from glpi_python_client.models.api_schema.assistance.timeline._document import (
    GetTimelineDocument,
)
from glpi_python_client.models.api_schema.assistance.timeline._followup import (
    GetFollowup,
)
from glpi_python_client.models.api_schema.assistance.timeline._solution import (
    GetSolution,
)
from glpi_python_client.models.api_schema.assistance.timeline._task import (
    GetTicketTask,
)


class GlpiTicketContext(GlpiModel):
    """Grouped public ticket context returned by ticket-context workflows.

    Parameters
    ----------
    ticket : GetTicket
        Primary ticket record returned by the GLPI API.
    tasks : list[GetTicketTask], optional
        Linked task records.
    followups : list[GetFollowup], optional
        Linked followup records.
    solutions : list[GetSolution], optional
        Linked solution records.
    documents : list[GetTimelineDocument], optional
        Linked timeline document records.
    """

    ticket: GetTicket
    tasks: list[GetTicketTask] = Field(default_factory=list)
    followups: list[GetFollowup] = Field(default_factory=list)
    solutions: list[GetSolution] = Field(default_factory=list)
    documents: list[GetTimelineDocument] = Field(default_factory=list)


__all__ = ["GlpiTicketContext"]
