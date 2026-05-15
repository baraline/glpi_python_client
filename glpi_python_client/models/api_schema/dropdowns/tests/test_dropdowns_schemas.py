"""Smoke tests for the dropdowns api_schema models."""

from __future__ import annotations

from glpi_python_client.models.api_schema.dropdowns import (
    DeleteLocation,
    GetLocation,
    PatchLocation,
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
