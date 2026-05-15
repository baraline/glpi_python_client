"""Typed GLPI ticket model.

The ticket model is the richest object in the package and can hold both the
core ticket fields and related timeline, document, and team data.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from glpi_python_client.content.conversion import GlpiContentConverter
from glpi_python_client.models._base import GlpiModel
from glpi_python_client.models._payload import (
    ApiPayloadMixin,
    drop_empty_payload_values,
)
from glpi_python_client.models._shared import _model_data
from glpi_python_client.models.glpi._document import GlpiDocument
from glpi_python_client.models.glpi._followup import GlpiFollowup
from glpi_python_client.models.glpi._solution import GlpiSolution
from glpi_python_client.models.glpi._task import GlpiTask
from glpi_python_client.models.glpi._team_member import GlpiTeamMember
from glpi_python_client.models.glpi._user import GlpiUser


def _glpi_user_from_value(value: object | None) -> GlpiUser | None:
    if value is None:
        return None
    if isinstance(value, GlpiUser):
        return value
    return GlpiUser.model_validate(_model_data(value))


def _datetime_from_data(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _glpi_followup_from_value(value: object) -> GlpiFollowup:
    if isinstance(value, GlpiFollowup):
        return value
    data = _model_data(value)
    author = _glpi_user_from_value(data.get("author"))
    author_id = data.get("author_id")
    if author is None and author_id is not None:
        author = GlpiUser(user_id=str(author_id))
    return GlpiFollowup(
        followup_id=_optional_text(data.get("followup_id")),
        content=GlpiContentConverter.from_transport(data.get("content")),
        created_at=_datetime_from_data(data.get("created_at")),
        updated_at=_datetime_from_data(data.get("updated_at")),
        author=author,
        editor=_glpi_user_from_value(data.get("editor")),
        is_private=bool(data.get("is_private", False)),
        attachment_document_ids=tuple(
            str(document_id) for document_id in data.get("attachment_document_ids", ())
        ),
    )


def _glpi_solution_from_value(value: object) -> GlpiSolution:
    if isinstance(value, GlpiSolution):
        return value
    data = _model_data(value)
    author = _glpi_user_from_value(data.get("author"))
    author_id = data.get("author_id")
    if author is None and author_id is not None:
        author = GlpiUser(user_id=str(author_id))
    return GlpiSolution(
        solution_id=_optional_text(data.get("solution_id")),
        content=GlpiContentConverter.from_transport(data.get("content")),
        created_at=_datetime_from_data(data.get("created_at")),
        updated_at=_datetime_from_data(data.get("updated_at")),
        author=author,
        attachment_document_ids=tuple(
            str(document_id) for document_id in data.get("attachment_document_ids", ())
        ),
    )


def _glpi_task_from_value(value: object) -> GlpiTask:
    if isinstance(value, GlpiTask):
        return value
    data = _model_data(value)
    author = _glpi_user_from_value(data.get("author"))
    author_id = data.get("author_id")
    if author is None and author_id is not None:
        author = GlpiUser(user_id=str(author_id))
    editor = _glpi_user_from_value(data.get("editor"))
    editor_id = data.get("editor_id")
    if editor is None and editor_id is not None:
        editor = GlpiUser(user_id=str(editor_id))
    return GlpiTask(
        task_id=_optional_text(data.get("task_id")),
        ticket_id=_optional_text(data.get("ticket_id")),
        user_id=_optional_text(data.get("user_id")),
        user=_glpi_user_from_value(data.get("user")),
        duration=(
            int(data.get("duration")) if data.get("duration") is not None else None
        ),
        date=_datetime_from_data(data.get("date")),
        content=GlpiContentConverter.from_transport(data.get("content")),
        created_at=_datetime_from_data(data.get("created_at")),
        updated_at=_datetime_from_data(data.get("updated_at")),
        author=author,
        editor=editor,
        is_private=bool(data.get("is_private", False)),
        entity=data.get("entity"),
        extra_payload=dict(data.get("extra_payload") or {}),
    )


def _glpi_document_from_value(value: object) -> GlpiDocument:
    if isinstance(value, GlpiDocument):
        return value
    return GlpiDocument.model_validate(_model_data(value))


def _glpi_team_member_from_value(value: object) -> GlpiTeamMember:
    if isinstance(value, GlpiTeamMember):
        return value
    return GlpiTeamMember.model_validate(_model_data(value))


def _normalize_glpi_ticket_updates(updates: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in updates.items():
        if key in {"user_recipient", "user_editor"}:
            normalized[key] = _glpi_user_from_value(value)
        elif key == "followups":
            normalized[key] = tuple(_glpi_followup_from_value(item) for item in value)
        elif key == "tasks":
            normalized[key] = tuple(_glpi_task_from_value(item) for item in value)
        elif key == "solutions":
            normalized[key] = tuple(_glpi_solution_from_value(item) for item in value)
        elif key == "documents":
            normalized[key] = tuple(_glpi_document_from_value(item) for item in value)
        elif key == "team":
            normalized[key] = tuple(
                _glpi_team_member_from_value(item) for item in value
            )
        else:
            normalized[key] = value
    return normalized


class GlpiTicket(ApiPayloadMixin, GlpiModel):
    """GLPI ticket record.

    Textual ``content`` is stored as canonical Markdown in Python. It is rendered
    to GLPI HTML only when :meth:`to_api_payload` builds an outgoing payload.
    """

    id: str | None = None
    name: str | None = None
    content: str | None = None
    status: int | dict[str, object] | None = None
    urgency: int | None = None
    impact: int | None = None
    priority: int | None = None
    type: int | None = None
    external_id: str | None = None
    category: int | dict[str, object] | None = None
    entity: int | dict[str, object] | None = None
    location: str | int | dict[str, object] | None = None
    request_type: str | dict[str, object] | None = None
    date_creation: datetime | None = None
    date_mod: datetime | None = None
    date_close: datetime | None = None
    user_recipient: GlpiUser | None = None
    user_editor: GlpiUser | None = None
    followups: tuple[GlpiFollowup, ...] = ()
    tasks: tuple[GlpiTask, ...] = ()
    solutions: tuple[GlpiSolution, ...] = ()
    documents: tuple[GlpiDocument, ...] = ()
    team: tuple[GlpiTeamMember, ...] = ()

    @classmethod
    def from_record(
        cls, record: GlpiTicket | Mapping[str, Any], **updates: Any
    ) -> GlpiTicket:
        """Build a ticket instance from an existing record and override values.

        The helper accepts either an existing ``GlpiTicket`` or a normalized
        mapping and then applies any requested updates through the same model
        validation path as direct construction.
        """

        if isinstance(record, cls):
            base_data = record.model_dump(mode="python")
        else:
            base_data = dict(record)
        if updates:
            base_data.update(_normalize_glpi_ticket_updates(updates))
        return cls.model_validate(base_data)

    def updated_at(self) -> datetime:
        """Return the best available update timestamp for the ticket.

        When GLPI does not provide ``date_mod``, the current local timestamp is
        used as a fallback so caller code always receives a ``datetime`` value.
        """

        return self.date_mod or datetime.now().astimezone()

    def _build_api_payload(
        self,
        *,
        entity_id: int | None = None,
        include_entity: bool = False,
        field_mask: tuple[str, ...] = (),
        category_defaults: Mapping[str, int] | Sequence[int] | None = None,
        default_status: int | None = None,
        default_priority: int | None = None,
        default_type: int | None = None,
    ) -> dict[str, object]:
        """Build the raw GLPI API request body for the ticket.

        The payload builder applies the package's defaulting rules for entity,
        status, priority, type, and category fields before optionally trimming
        the result with a field mask.
        """

        status = (
            _glpi_field_id(self.status)
            if self.status is not None
            else (default_status if include_entity else None)
        )
        priority = (
            self.priority
            if self.priority is not None
            else (default_priority if include_entity else None)
        )
        glpi_type = (
            self.type
            if self.type is not None
            else (default_type if include_entity else None)
        )
        category = _glpi_field_id(self.category) or _category_from_defaults(
            category_defaults, _glpi_field_name(self.category)
        )
        payload = drop_empty_payload_values(
            {
                "name": self.name,
                "content": GlpiContentConverter.to_transport(self.content)
                if self.content is not None
                else None,
                "status": _id_object(status),
                "urgency": self.urgency,
                "impact": self.impact,
                "priority": priority,
                "type": glpi_type,
                "external_id": self.external_id,
                "category": _id_object(category),
                "location": _id_object(_glpi_field_id(self.location)),
                "entity": _id_object(
                    entity_id if entity_id is not None else _glpi_field_id(self.entity)
                )
                if include_entity
                else None,
            }
        )
        if not field_mask:
            return payload
        return {key: value for key, value in payload.items() if key in field_mask}


def _optional_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _id_object(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    return {"id": value}


def _glpi_field_id(value: object) -> object | None:
    if isinstance(value, Mapping):
        return value.get("id")
    return value


def _glpi_field_name(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    text = str(value.get("name", "")).strip()
    return text or None


def _category_from_defaults(
    category_defaults: Mapping[str, int] | Sequence[int] | None,
    category_label: str | None,
) -> object | None:
    if not category_defaults:
        return None
    if isinstance(category_defaults, Mapping):
        if category_label:
            expected = category_label.casefold()
            for key, value in category_defaults.items():
                if str(key).casefold() == expected:
                    return value
        return None
    for value in category_defaults:
        if value is not None:
            return value
    return None


__all__ = ["GlpiTicket"]
