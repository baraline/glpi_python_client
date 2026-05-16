"""Aggregated ticket context view bundling timeline records.

The ticket context model gathers the primary ticket record together with
the most common timeline records (followups, tasks, solutions) and any
linked documents. It is consumed by higher-level workflows that need a
single object to reason about a ticket and its history.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
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


def _render_value(value: object | None) -> str | None:
    """Convert one supported metadata value into a display string.

    The ticket-context Markdown view reuses one compact subtitle format
    across the main ticket and every timeline item. This helper keeps
    the formatting rules consistent for timestamps, GLPI references,
    and enum values while leaving plain strings unchanged.
    """

    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, IdNameRef):
        return _ref_label(value)
    if isinstance(value, Enum):
        return value.name.replace("_", " ").title()
    return str(value)


def _subtitle_line(*parts: tuple[str, object | None]) -> str | None:
    """Build one Markdown subtitle line from labeled metadata values.

    Missing values are skipped so callers can pass the full set of
    potentially interesting fields without having to pre-filter them.
    The subtitle is emitted as one Markdown blockquote line to make the
    metadata visually distinct from the section body.
    """

    rendered_parts = []
    for label, value in parts:
        rendered_value = _render_value(value)
        if rendered_value:
            rendered_parts.append(f"{label}: {rendered_value}")
    if not rendered_parts:
        return None
    return f"> {' | '.join(rendered_parts)}"


def _event_sort_key(event: Any) -> datetime:
    """Compute the sort key used to order timeline events for rendering.

    Ticket context rendering must follow the actual activity chronology,
    not the left/right anchoring hint used by the GLPI chat UI. Entries
    are therefore always ordered by ``date_creation`` and items missing a
    creation timestamp are pushed to the end while preserving the sort's
    stability.
    """

    return getattr(event, "date_creation", None) or _MAX_DATETIME


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

        The rendering starts with the ticket title, then a compact
        subtitle line containing the requester, last editor, and the
        key timestamps exposed by the public ticket model. The ticket
        body is separated from the timeline itself, and each followup,
        task, and solution receives its own heading plus a metadata
        subtitle. Timeline entries are always sorted by ``date_creation``
        so the transcript follows the actual chronology rather than the
        GLPI UI anchoring hints. Linked documents are still appended in a
        dedicated section because the document-link payload does not
        expose the same authoring metadata.

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

        ticket_subtitle = _subtitle_line(
            ("Status", ticket.status),
            ("Requester", ticket.user_recipient),
            ("Last edited by", ticket.user_editor),
            ("Created at", ticket.date_creation),
            ("Updated at", ticket.date_mod),
            ("Resolved at", ticket.date_solve),
            ("Closed at", ticket.date_close),
        )
        if ticket_subtitle is not None:
            lines.append(ticket_subtitle)

        if ticket.content:
            lines.append("")
            lines.append("## Description")
            lines.append("")
            lines.append(ticket.content)

        events: list[tuple[str, Any]] = []
        events.extend(("Followup", item) for item in self.followups)
        events.extend(("Task", item) for item in self.tasks)
        events.extend(("Solution", item) for item in self.solutions)
        events.sort(key=lambda pair: _event_sort_key(pair[1]))

        if events:
            lines.append("")
            lines.append("## Timeline")

        for kind, event in events:
            event_id = getattr(event, "id", None)
            heading = (
                f"### {kind} #{event_id}" if event_id is not None else f"### {kind}"
            )
            lines.append("")
            lines.append(heading)

            event_subtitle = _subtitle_line(
                ("Created by", getattr(event, "user", None)),
                ("Last edited by", getattr(event, "user_editor", None)),
                ("Created at", getattr(event, "date_creation", None)),
                ("Updated at", getattr(event, "date_mod", None)),
                ("Scheduled for", getattr(event, "date", None)),
                ("Planned start", getattr(event, "planned_begin", None)),
                ("Planned end", getattr(event, "planned_end", None)),
                ("Approved at", getattr(event, "date_approval", None)),
                ("State", getattr(event, "state", None)),
                ("Status", getattr(event, "status", None)),
                (
                    "Duration",
                    (
                        f"{duration}s"
                        if (duration := getattr(event, "duration", None)) is not None
                        else None
                    ),
                ),
                ("Technician", getattr(event, "user_tech", None)),
                ("Technician group", getattr(event, "group_tech", None)),
                ("Approver", getattr(event, "approver", None)),
            )
            if event_subtitle is not None:
                lines.append(event_subtitle)

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
