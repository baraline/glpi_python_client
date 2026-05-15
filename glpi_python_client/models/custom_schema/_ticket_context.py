"""Aggregated ticket context view bundling timeline records.

The ticket context model gathers the primary ticket record together with
the most common timeline records (followups, tasks, solutions) and any
linked documents. It is consumed by higher-level workflows that need a
single object to reason about a ticket and its history.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models.api_schema._common import IdNameRef
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
from glpi_python_client.models.api_schema.enums import GlpiTimelinePosition

_MAX_DATETIME = datetime.max


def _ref_label(ref: IdNameRef | None) -> str | None:
    """Return the human-readable label of one ``IdNameRef`` reference.

    The helper prefers ``name`` (the GLPI display label) and falls back to
    the numeric identifier when the server only returned the foreign key.
    Returns ``None`` when the reference itself is missing so callers can
    omit the field from the rendered Markdown.
    """

    if ref is None:
        return None
    if ref.name:
        return ref.name
    if ref.id is not None:
        return f"#{ref.id}"
    return None


def _event_sort_key(event: Any) -> tuple[int, int, datetime]:
    """Compute the sort key used to order timeline events for rendering.

    Events with a meaningful ``timeline_position`` (a positive
    :class:`GlpiTimelinePosition` member) come first in position order so
    the rendered transcript matches the GLPI UI layout. The remaining
    events fall back to ``date_creation``; events missing both attributes
    are pushed to the end with a stable ordering.
    """

    position = getattr(event, "timeline_position", None)
    fallback_date = getattr(event, "date_creation", None) or _MAX_DATETIME
    if isinstance(position, GlpiTimelinePosition) and position.value > 0:
        return (0, position.value, fallback_date)
    return (1, 0, fallback_date)


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

    def to_markdown(self) -> str:
        """Render the ticket and its timeline as one Markdown transcript.

        The header reports the ticket identifier, name, status, and body,
        followed by every timeline event (followups, tasks, solutions)
        sorted by ``timeline_position`` when set and otherwise by
        ``date_creation``. Linked documents are appended at the end as a
        bullet list because the timeline document link payload does not
        carry a creation timestamp. Empty fields are omitted so the
        output stays compact regardless of how complete the GLPI payload
        is.

        Returns
        -------
        str
            Markdown transcript suitable for direct display or for
            forwarding into a downstream Markdown renderer. The string
            never ends with trailing whitespace.
        """

        lines: list[str] = []
        ticket = self.ticket
        ticket_label = ticket.name or "(unnamed ticket)"
        if ticket.id is not None:
            lines.append(f"# Ticket #{ticket.id} \u2014 {ticket_label}")
        else:
            lines.append(f"# Ticket \u2014 {ticket_label}")
        status_label = _ref_label(ticket.status)
        if status_label is not None:
            lines.append(f"- **Status**: {status_label}")
        if ticket.content:
            lines.append("")
            lines.append(ticket.content)

        events: list[tuple[str, Any]] = []
        events.extend(("Followup", item) for item in self.followups)
        events.extend(("Task", item) for item in self.tasks)
        events.extend(("Solution", item) for item in self.solutions)
        events.sort(key=lambda pair: _event_sort_key(pair[1]))

        for kind, event in events:
            event_id = getattr(event, "id", None)
            heading = f"## {kind} #{event_id}" if event_id is not None else f"## {kind}"
            lines.append("")
            lines.append(heading)
            author_label = _ref_label(getattr(event, "user", None))
            if author_label is not None:
                lines.append(f"- **Author**: {author_label}")
            created = getattr(event, "date_creation", None)
            if created is not None:
                lines.append(f"- **Created**: {created.isoformat()}")
            duration = getattr(event, "duration", None)
            if duration is not None:
                lines.append(f"- **Duration**: {duration}s")
            content = getattr(event, "content", None)
            if content:
                lines.append("")
                lines.append(content)

        if self.documents:
            lines.append("")
            lines.append("## Documents")
            for document in self.documents:
                identifier = document.documents_id or document.id
                label = document.filepath or (
                    f"document #{identifier}" if identifier is not None else "document"
                )
                lines.append(f"- {label}")

        return "\n".join(lines).rstrip()


__all__ = ["GlpiTicketContext"]
