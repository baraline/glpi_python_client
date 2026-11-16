"""Smoke tests for the dropdowns api_schema models."""

from __future__ import annotations

from glpi_python_client.models.api_schema.dropdowns import (
    DeleteITILCategory,
    DeleteLocation,
    GetITILCategory,
    GetLocation,
    PatchITILCategory,
    PatchLocation,
    PostITILCategory,
    PostLocation,
)


def test_get_location_full_payload() -> None:
    """``GetLocation`` accepts every contract field of the ``Location`` schema."""

    payload = {
        "id": 3,
        "name": "Office",
        "completename": "HQ > Office",
        "code": "OFF",
        "alias": "off",
        "comment": "main office",
        "entity": {"id": 0, "name": "root"},
        "is_recursive": True,
        "parent": {"id": 1, "name": "HQ"},
        "level": 2,
        "room": "101",
        "building": "A",
        "address": "1 rue",
        "town": "Paris",
        "postcode": "75000",
        "state": "IDF",
        "country": "FR",
        "latitude": "48.8",
        "longitude": "2.3",
        "altitude": "35",
    }
    loc = GetLocation.model_validate(payload)
    assert loc.completename == "HQ > Office"
    assert loc.entity is not None
    assert loc.entity.id == 0


def test_post_location_rejects_read_only_fields() -> None:
    """Read-only location fields land in ``extra_payload`` for server-side rejection."""

    for forbidden in ("id", "completename", "level"):
        loc = PostLocation.model_validate({"name": "Office", forbidden: "x"})
        assert loc.extra_payload == {forbidden: "x"}


def test_patch_location_partial_body() -> None:
    """``PatchLocation`` accepts a partial body."""

    PatchLocation.model_validate({"comment": "moved"})


def test_delete_location_default() -> None:
    """``DeleteLocation`` exposes ``force`` as optional."""

    assert DeleteLocation().force is None


def test_get_itil_category_full_payload() -> None:
    """``GetITILCategory`` accepts every contract field of ``ITILCategory``."""

    ref = {"id": 5, "name": "ref"}
    payload = {
        "id": 3,
        "name": "Network",
        "completename": "IT > Network",
        "level": 2,
        "comment": "network issues",
        "entity": {"id": 7, "name": "root"},
        "is_recursive": True,
        "parent": {"id": 1, "name": "IT"},
        "user": ref,
        "group": ref,
        "code": "NET",
        "is_helpdesk_visible": True,
        "ticket_incident_template": ref,
        "ticket_request_template": ref,
        "change_template": ref,
        "problem_template": ref,
        "is_incident_visible": True,
        "is_request_visible": False,
        "is_change_visible": True,
        "is_problem_visible": False,
        "knowbase_category": ref,
        "date_creation": "2026-01-02T03:04:05+00:00",
        "date_mod": "2026-01-03T03:04:05+00:00",
    }
    category = GetITILCategory.model_validate(payload)
    assert category.completename == "IT > Network"
    assert category.level == 2
    assert category.entity is not None
    assert category.entity.id == 7
    assert category.parent is not None
    assert category.parent.id == 1
    assert category.knowbase_category is not None
    assert category.is_request_visible is False
    assert category.date_mod is not None
    assert category.extra_payload == {}


def test_post_itil_category_rejects_read_only_fields() -> None:
    """Read-only fields land in ``extra_payload`` for server-side rejection."""

    for forbidden in ("id", "completename", "level"):
        category = PostITILCategory.model_validate({"name": "Net", forbidden: "x"})
        assert category.extra_payload == {forbidden: "x"}


def test_patch_itil_category_partial_body() -> None:
    """``PatchITILCategory`` accepts a partial body."""

    PatchITILCategory.model_validate({"comment": "moved"})


def test_delete_itil_category_default() -> None:
    """``DeleteITILCategory`` exposes ``force`` as optional."""

    assert DeleteITILCategory().force is None
    assert DeleteITILCategory(force=True).force is True
