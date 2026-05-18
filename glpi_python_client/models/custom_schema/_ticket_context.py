"""Aggregated ticket context view bundling timeline records.

The ticket context model gathers the primary ticket record together with
the most common timeline records (followups, tasks, solutions) and any
linked documents. It is consumed by higher-level workflows that need a
single object to reason about a ticket and its history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class TicketMarkdownOptions:
    """Options controlling which sections and fields appear in the Markdown export.

    All flags default to ``True`` so that a bare ``to_markdown()`` call
    reproduces the original full output.

    Parameters
    ----------
    include_description : bool
        Emit the ``## Description`` section with the ticket body.
    include_followups : bool
        Include followup entries in the ``## Timeline`` section.
    include_tasks : bool
        Include task entries in the ``## Timeline`` section.
    include_solutions : bool
        Include solution entries in the ``## Timeline`` section.
    include_documents : bool
        Append the ``## Documents`` section with linked file references.
    show_status : bool
        Emit the ``Status`` field in the ticket subtitle line.
    show_requester : bool
        Emit the ``Requester`` field in the ticket subtitle line.
    show_editor : bool
        Emit the ``Last edited by`` field in the ticket subtitle line.
    show_dates : bool
        Emit all ticket-level date fields (created, updated, resolved,
        closed) in the ticket subtitle line.
    show_event_author : bool
        Emit the ``Created by`` field in timeline-entry subtitle lines.
    show_event_editor : bool
        Emit the ``Last edited by`` field in timeline-entry subtitle lines.
    show_event_dates : bool
        Emit date fields (created, updated, scheduled, planned start/end,
        approved) in timeline-entry subtitle lines.
    show_event_state : bool
        Emit the ``State`` field in timeline-entry subtitle lines.
    show_event_status : bool
        Emit the ``Status`` field in timeline-entry subtitle lines.
    show_duration : bool
        Emit the ``Duration`` field in task subtitle lines.
    show_technician : bool
        Emit the ``Technician`` and ``Technician group`` fields in task
        subtitle lines.
    show_approver : bool
        Emit the ``Approver`` field in solution subtitle lines.
    """

    include_description: bool = field(default=True)
    include_followups: bool = field(default=True)
    include_tasks: bool = field(default=True)
    include_solutions: bool = field(default=True)
    include_documents: bool = field(default=True)
    show_status: bool = field(default=True)
    show_requester: bool = field(default=True)
    show_editor: bool = field(default=True)
    show_dates: bool = field(default=True)
    show_event_author: bool = field(default=True)
    show_event_editor: bool = field(default=True)
    show_event_dates: bool = field(default=True)
    show_event_state: bool = field(default=True)
    show_event_status: bool = field(default=True)
    show_duration: bool = field(default=True)
    show_technician: bool = field(default=True)
    show_approver: bool = field(default=True)


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

    def to_markdown(
        self,
        options: TicketMarkdownOptions | None = None,
    ) -> str:
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

        Parameters
        ----------
        options : TicketMarkdownOptions, optional
            Controls which sections and metadata fields are included in
            the output. When *None* (the default) a fresh
            :class:`TicketMarkdownOptions` is used, which enables all
            sections and fields.

        Returns
        -------
        str
            Markdown transcript suitable for direct display or for
            forwarding into a downstream Markdown renderer. The string
            never ends with trailing whitespace.
        """

        opts = options if options is not None else TicketMarkdownOptions()

        lines: list[str] = []
        ticket = self.ticket
        ticket_label = ticket.name or "(unnamed ticket)"
        if ticket.id is not None:
            lines.append(f"# Ticket #{ticket.id} \u2014 {ticket_label}")
        else:
            lines.append(f"# Ticket \u2014 {ticket_label}")

        ticket_subtitle_parts: list[tuple[str, object | None]] = []
        if opts.show_status:
            ticket_subtitle_parts.append(("Status", ticket.status))
        if opts.show_requester:
            ticket_subtitle_parts.append(("Requester", ticket.user_recipient))
        if opts.show_editor:
            ticket_subtitle_parts.append(("Last edited by", ticket.user_editor))
        if opts.show_dates:
            ticket_subtitle_parts += [
                ("Created at", ticket.date_creation),
                ("Updated at", ticket.date_mod),
                ("Resolved at", ticket.date_solve),
                ("Closed at", ticket.date_close),
            ]
        ticket_subtitle = _subtitle_line(*ticket_subtitle_parts)
        if ticket_subtitle is not None:
            lines.append(ticket_subtitle)

        if opts.include_description and ticket.content:
            lines.append("")
            lines.append("## Description")
            lines.append("")
            lines.append(ticket.content)

        events: list[tuple[str, Any]] = []
        if opts.include_followups:
            events.extend(("Followup", item) for item in self.followups)
        if opts.include_tasks:
            events.extend(("Task", item) for item in self.tasks)
        if opts.include_solutions:
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

            event_subtitle_parts: list[tuple[str, object | None]] = []
            if opts.show_event_author:
                event_subtitle_parts.append(
                    ("Created by", getattr(event, "user", None))
                )
            if opts.show_event_editor:
                event_subtitle_parts.append(
                    ("Last edited by", getattr(event, "user_editor", None))
                )
            if opts.show_event_dates:
                event_subtitle_parts += [
                    ("Created at", getattr(event, "date_creation", None)),
                    ("Updated at", getattr(event, "date_mod", None)),
                    ("Scheduled for", getattr(event, "date", None)),
                    ("Planned start", getattr(event, "planned_begin", None)),
                    ("Planned end", getattr(event, "planned_end", None)),
                    ("Approved at", getattr(event, "date_approval", None)),
                ]
            if opts.show_event_state:
                event_subtitle_parts.append(("State", getattr(event, "state", None)))
            if opts.show_event_status:
                event_subtitle_parts.append(("Status", getattr(event, "status", None)))
            if opts.show_duration:
                duration = getattr(event, "duration", None)
                event_subtitle_parts.append(
                    ("Duration", f"{duration}s" if duration is not None else None)
                )
            if opts.show_technician:
                event_subtitle_parts += [
                    ("Technician", getattr(event, "user_tech", None)),
                    ("Technician group", getattr(event, "group_tech", None)),
                ]
            if opts.show_approver:
                event_subtitle_parts.append(
                    ("Approver", getattr(event, "approver", None))
                )
            event_subtitle = _subtitle_line(*event_subtitle_parts)
            if event_subtitle is not None:
                lines.append(event_subtitle)

            content = getattr(event, "content", None)
            if content:
                lines.append("")
                lines.append(content)

        if opts.include_documents and self.documents:
            lines.append("")
            lines.append("## Documents")
            for document in self.documents:
                identifier = document.documents_id or document.id
                label = document.filepath or (
                    f"document #{identifier}" if identifier is not None else "document"
                )
                lines.append(f"- {label}")

        return "\n".join(lines).rstrip()


__all__ = ["GlpiTicketContext", "TicketMarkdownOptions"]
