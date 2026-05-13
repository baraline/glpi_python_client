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
from glpi_python_client.content.records.core.references import _glpi_id_value
from glpi_python_client.content.records.core.scalars import (
    _coerce_bool,
    _optional_text,
    _parse_glpi_datetime,
)
from glpi_python_client.models import GlpiFollowup, GlpiSolution, GlpiTask, GlpiUser


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
    author_id = _glpi_author_id(raw_task)
    editor = raw_task.get("user_editor")
    editor_id = _optional_text(_glpi_id_value(editor))
    return GlpiTask(
        task_id=task_id,
        content=GlpiContentConverter.from_transport(raw_task.get("content")),
        created_at=_parse_glpi_datetime(
            raw_task.get("date_creation") or raw_task.get("date")
        ),
        updated_at=_parse_glpi_datetime(
            raw_task.get("date_mod") or raw_task.get("date")
        ),
        author=GlpiUser(user_id=author_id) if author_id is not None else None,
        editor=GlpiUser(user_id=editor_id) if editor_id is not None else None,
        is_private=_coerce_bool(raw_task.get("is_private")),
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
