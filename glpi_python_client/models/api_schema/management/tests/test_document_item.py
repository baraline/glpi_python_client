"""Tests for the ``GetDocumentItem`` link-row model."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from glpi_python_client.models.api_schema.assistance.timeline import GetFollowup
from glpi_python_client.models.api_schema.enums import GlpiTimelinePosition
from glpi_python_client.models.api_schema.management import (
    FollowupDocuments,
    GetDocumentItem,
)

_PARIS_SUMMER = timezone(timedelta(hours=2))


def _row(**overrides: object) -> dict[str, object]:
    """Return one v1 ``Document_Item`` row with synthetic values."""

    row: dict[str, object] = {
        "id": 7,
        "documents_id": 11,
        "items_id": 42,
        "itemtype": "ITILFollowup",
        "entities_id": 3,
        "is_recursive": 0,
        "date_mod": "2024-01-02 03:04:05",
        "date_creation": "2024-01-02 03:04:06",
        "date": "2024-01-02 03:04:07",
        "users_id": 5,
        "timeline_position": 1,
        "links": [{"rel": "Document", "href": "https://example.invalid/Document/11"}],
    }
    row.update(overrides)
    return row


def test_full_v1_row_builds_the_model() -> None:
    """Every declared field is read and the rest lands in ``extra_payload``."""

    item = GetDocumentItem.model_validate(_row())
    assert (item.id, item.documents_id, item.items_id) == (7, 11, 42)
    assert item.itemtype == "ITILFollowup"
    assert item.entities_id == 3
    assert item.date_creation == datetime(2024, 1, 2, 3, 4, 6)
    assert item.date_mod == datetime(2024, 1, 2, 3, 4, 5)
    assert item.date == datetime(2024, 1, 2, 3, 4, 7)
    assert item.extra_payload["users_id"] == 5
    assert item.extra_payload["is_recursive"] == 0


def test_row_without_documents_id_is_rejected() -> None:
    """The document id is the one field a link row cannot do without."""

    row = _row()
    del row["documents_id"]
    with pytest.raises(ValidationError):
        GetDocumentItem.model_validate(row)


def test_row_without_id_is_rejected() -> None:
    """The row id is required."""

    row = _row()
    del row["id"]
    with pytest.raises(ValidationError):
        GetDocumentItem.model_validate(row)


def test_minus_one_reads_no_timeline() -> None:
    """A link at -1 is the editor's embedded-image marker."""

    item = GetDocumentItem.model_validate(_row(timeline_position=-1))
    assert item.timeline_position is GlpiTimelinePosition.NO_TIMELINE
    assert "timeline_position" not in item.extra_payload


def test_no_timeline_is_an_alias_of_invalid() -> None:
    """``NO_TIMELINE`` is GLPI's own name for the value ``INVALID`` already holds."""

    assert GlpiTimelinePosition.NO_TIMELINE is GlpiTimelinePosition.INVALID
    assert GlpiTimelinePosition.NO_TIMELINE == -1
    assert GlpiTimelinePosition(-1) is GlpiTimelinePosition.INVALID
    assert GlpiTimelinePosition(-1).name == "INVALID"


def test_one_reads_left() -> None:
    """A link at 1 is an uploaded document."""

    item = GetDocumentItem.model_validate(_row(timeline_position=1))
    assert item.timeline_position is GlpiTimelinePosition.LEFT


def test_missing_timeline_position_reads_none() -> None:
    """A row without the field leaves it unset."""

    row = _row()
    del row["timeline_position"]
    assert GetDocumentItem.model_validate(row).timeline_position is None


def test_links_land_in_extra_payload() -> None:
    """The HATEOAS ``links`` list is kept untouched in ``extra_payload``."""

    item = GetDocumentItem.model_validate(_row())
    assert item.extra_payload["links"] == [
        {"rel": "Document", "href": "https://example.invalid/Document/11"}
    ]


def test_naive_datetimes_are_localised_to_the_server_timezone() -> None:
    """Naive timestamps gain the server timezone from the validation context."""

    item = GetDocumentItem.model_validate(
        _row(), context={"server_timezone": _PARIS_SUMMER}
    )
    assert item.date_creation is not None
    assert item.date_creation.tzinfo == _PARIS_SUMMER
    assert item.date_mod is not None
    assert item.date_mod.tzinfo == _PARIS_SUMMER
    assert item.date is not None
    assert item.date.tzinfo == _PARIS_SUMMER


def test_followup_documents_holds_a_followup_and_its_links() -> None:
    """The result model carries the followup whole and is frozen."""

    entry = FollowupDocuments(
        followup=GetFollowup.model_validate({"id": 42, "is_private": False}),
        documents=[GetDocumentItem.model_validate(_row())],
    )
    assert entry.followup.is_private is False
    assert entry.documents[0].documents_id == 11
    with pytest.raises(ValidationError):
        entry.documents = []
