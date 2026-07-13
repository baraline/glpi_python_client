"""Tests for the Knowledge base category api_schema models."""

from __future__ import annotations

from glpi_python_client.models.api_schema.knowledgebase import (
    DeleteKBCategory,
    GetKBCategory,
    PatchKBCategory,
    PostKBCategory,
)


def test_get_kb_category_full_payload() -> None:
    """``GetKBCategory`` accepts every contract field of ``KBCategory``."""

    payload = {
        "id": 4,
        "name": "Network",
        "completename": "IT > Network",
        "comment": "networking articles",
        "entity": {"id": 0, "name": "root"},
        "is_recursive": True,
        "parent": {"id": 1, "name": "IT"},
        "level": 2,
        "date_creation": "2026-01-02T09:00:00+00:00",
        "date_mod": "2026-01-03T09:00:00+00:00",
    }
    category = GetKBCategory.model_validate(payload)
    assert category.id == 4
    assert category.completename == "IT > Network"
    assert category.parent is not None
    assert category.parent.id == 1


def test_post_kb_category_routes_read_only_fields_to_extra() -> None:
    """Read-only fields land in ``extra_payload`` for server-side rejection."""

    for forbidden in ("id", "completename", "level"):
        category = PostKBCategory.model_validate({"name": "Network", forbidden: "x"})
        assert category.extra_payload == {forbidden: "x"}


def test_patch_kb_category_partial_body() -> None:
    """``PatchKBCategory`` accepts a partial body."""

    PatchKBCategory.model_validate({"comment": "moved"})


def test_delete_kb_category_force_default() -> None:
    """``DeleteKBCategory`` exposes ``force`` as optional."""

    assert DeleteKBCategory().force is None
