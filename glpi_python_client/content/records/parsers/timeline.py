"""GLPI timeline record parsing helpers.

This module converts followup, solution, and task timeline payloads into their
typed rich-model equivalents.
"""

from __future__ import annotations

from typing import Any

from glpi_python_client.content.conversion import GlpiContentConverter
from glpi_python_client.content.records.core.document_links import (
    _glpi_followup_attachment_document_ids,
    _strip_glpi_document_references,
)
from glpi_python_client.content.records.core.references import (
    _glpi_id_reference,
    _glpi_id_value,
    _glpi_ticket_user_payload,
)
from glpi_python_client.content.records.core.scalars import (
    _coerce_bool,
    _optional_int,
    _optional_text,
    _parse_glpi_datetime,
)
from glpi_python_client.models import GlpiFollowup, GlpiSolution, GlpiTask, GlpiUser

_KNOWN_TASK_FIELDS = {
    "id",
    "content",
    "date",
    "date_creation",
    "date_mod",
    "users_id",
    "user",
    "user_editor",
    "is_private",
    "tickets_id",
    "ticket",
    "actiontime",
    "duration",
    "entity",
    "entities_id",
}


def _glpi_followup_record(raw_followup: dict[str, Any]) -> GlpiFollowup:
    """Build a ``GlpiFollowup`` from one raw timeline payload.

    Followup parsing strips inline document references from the human-readable
    content while extracting attachment document IDs separately.
    """

    followup_id = _optional_text(raw_followup.get("id"))
    if followup_id is None:
        raise ValueError("GLPI followup payload did not include an ID")
    raw_content = str(raw_followup.get("content") or "")
    author_id = _glpi_author_id(raw_followup)
    return GlpiFollowup(
        followup_id=followup_id,
        content=GlpiContentConverter.from_transport(
            _strip_glpi_document_references(raw_content)
        ),
        created_at=_parse_glpi_datetime(raw_followup.get("date_creation")),
        updated_at=_parse_glpi_datetime(raw_followup.get("date_mod")),
        author=GlpiUser(user_id=author_id) if author_id is not None else None,
        is_private=_coerce_bool(raw_followup.get("is_private")),
        attachment_document_ids=_glpi_followup_attachment_document_ids(raw_content),
    )


def _glpi_solution_record(raw_solution: dict[str, Any]) -> GlpiSolution:
    """Build a ``GlpiSolution`` from one raw solution payload.

    Solutions share most of the same parsing rules as followups, including
    attachment extraction and Markdown normalization.
    """

    solution_id = _optional_text(raw_solution.get("id"))
    if solution_id is None:
        raise ValueError("GLPI solution payload did not include an ID")
    raw_content = str(raw_solution.get("content") or "")
    author_id = _glpi_author_id(raw_solution)
    return GlpiSolution(
        solution_id=solution_id,
        content=GlpiContentConverter.from_transport(
            _strip_glpi_document_references(raw_content)
        ),
        created_at=_parse_glpi_datetime(raw_solution.get("date_creation")),
        updated_at=_parse_glpi_datetime(raw_solution.get("date_mod")),
        author=GlpiUser(user_id=author_id) if author_id is not None else None,
        attachment_document_ids=_glpi_followup_attachment_document_ids(raw_content),
    )


def _glpi_task_record(raw_task: dict[str, Any]) -> GlpiTask:
    """Build a ``GlpiTask`` from one raw task payload.

    Tasks can encode their dates under multiple keys, so the parser checks the
    known GLPI variants before building the typed task object.
    """

    task_id = _optional_text(raw_task.get("id"))
    if task_id is None:
        raise ValueError("GLPI task payload did not include an ID")
    user = _glpi_task_user(raw_task)
    user_id = user.user_id if user is not None else _glpi_author_id(raw_task)
    if user is None and user_id is not None:
        user = GlpiUser(user_id=user_id)
    editor = _glpi_task_editor(raw_task)
    return GlpiTask(
        task_id=task_id,
        ticket_id=_optional_text(
            raw_task.get("tickets_id") or _glpi_id_value(raw_task.get("ticket"))
        ),
        user_id=user_id,
        user=user,
        duration=_optional_int(raw_task.get("actiontime") or raw_task.get("duration")),
        date=_parse_glpi_datetime(raw_task.get("date")),
        content=GlpiContentConverter.from_transport(raw_task.get("content")),
        created_at=_parse_glpi_datetime(
            raw_task.get("date_creation") or raw_task.get("date")
        ),
        updated_at=_parse_glpi_datetime(
            raw_task.get("date_mod") or raw_task.get("date")
        ),
        author=user,
        editor=editor,
        is_private=_coerce_bool(raw_task.get("is_private")),
        entity=_glpi_id_reference(
            raw_task.get("entity") or raw_task.get("entities_id")
        ),
        extra_payload={
            key: value
            for key, value in raw_task.items()
            if key not in _KNOWN_TASK_FIELDS
        },
    )


def _glpi_author_id(raw_item: dict[str, Any]) -> str | None:
    """Extract the most specific GLPI author identifier from one payload.

    The helper prefers nested user mappings before falling back to the older
    scalar ``users_id`` field.
    """

    user_payload = raw_item.get("user")
    if isinstance(user_payload, dict):
        user_id = _optional_text(user_payload.get("id"))
        if user_id is not None:
            return user_id
    editor_payload = raw_item.get("user_editor")
    if isinstance(editor_payload, dict):
        user_id = _optional_text(editor_payload.get("id"))
        if user_id is not None:
            return user_id
    return _optional_text(raw_item.get("users_id"))


def _glpi_task_user(raw_task: dict[str, Any]) -> GlpiUser | None:
    """Return the best parsed task user from one raw GLPI task payload.

    The helper prefers the explicit nested ``user`` object and falls back to a
    lightweight user built from ``users_id`` when only the identifier is
    available.
    """

    user = _glpi_ticket_user_payload(raw_task.get("user"))
    if user is not None:
        return user
    user_id = _optional_text(raw_task.get("users_id"))
    if user_id is None:
        return None
    return GlpiUser(user_id=user_id)


def _glpi_task_editor(raw_task: dict[str, Any]) -> GlpiUser | None:
    """Return the best parsed task editor from one raw GLPI task payload.

    GLPI may return the editor as a nested partial user record or only by ID.
    This helper keeps the public model consistent across both payload shapes.
    """

    editor = _glpi_ticket_user_payload(raw_task.get("user_editor"))
    if editor is not None:
        return editor
    editor_payload = raw_task.get("user_editor")
    editor_id = _optional_text(_glpi_id_value(editor_payload))
    if editor_id is None:
        return None
    return GlpiUser(user_id=editor_id)
