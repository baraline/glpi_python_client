"""Public ticket context bundle model.

The ticket context model groups the primary ticket record with the most common
timeline and document records needed by higher-level workflows.
"""

from __future__ import annotations

from pydantic import Field

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.glpi._document import GlpiDocument
from glpi_python_client.models.glpi._followup import GlpiFollowup
from glpi_python_client.models.glpi._solution import GlpiSolution
from glpi_python_client.models.glpi._task import GlpiTask
from glpi_python_client.models.glpi._ticket import GlpiTicket


class GlpiTicketContext(GlpiModel):
    """Grouped public ticket context returned by ``get_ticket_context``.

    Parameters
    ----------
    ticket : GlpiTicket
        Primary ticket record.
    tasks : list[GlpiTask], optional
        Linked task records.
    followups : list[GlpiFollowup], optional
        Linked followup records.
    solutions : list[GlpiSolution], optional
        Linked solution records.
    documents : list[GlpiDocument], optional
        Linked document records.
    """

    ticket: GlpiTicket
    tasks: list[GlpiTask] = Field(default_factory=list)
    followups: list[GlpiFollowup] = Field(default_factory=list)
    solutions: list[GlpiSolution] = Field(default_factory=list)
    documents: list[GlpiDocument] = Field(default_factory=list)
