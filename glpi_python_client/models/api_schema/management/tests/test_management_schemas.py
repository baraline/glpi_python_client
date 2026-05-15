"""Smoke tests for the management api_schema models."""

from __future__ import annotations

from glpi_python_client.models.api_schema.management import (
    DeleteDocument,
    GetDocument,
    PatchDocument,
    PostDocument,
)


def test_get_document_full_payload() -> None:
    """``GetDocument`` accepts every contract field of the ``Document`` schema."""

    payload = {
        "id": 9,
        "name": "report",
        "comment": "yearly",
        "entity": {"id": 0, "name": "root"},
        "date_creation": "2024-01-02T03:04:05",
        "date_mod": "2024-02-03T04:05:06",
        "is_deleted": False,
        "filename": "report.pdf",
        "filepath": "PDF/report.pdf",
        "mime": "application/pdf",
        "sha1sum": "deadbeef",
    }
    doc = GetDocument.model_validate(payload)
    assert doc.filename == "report.pdf"


def test_post_document_rejects_read_only_fields() -> None:
    """Read-only document fields land in ``extra_payload`` for server-side rejection."""

    for forbidden in ("id", "filepath"):
        doc = PostDocument.model_validate({"name": "x", forbidden: "v"})
        assert doc.extra_payload == {forbidden: "v"}


def test_patch_document_partial_body() -> None:
    """``PatchDocument`` accepts a partial body."""

    PatchDocument.model_validate({"comment": "renamed"})


def test_delete_document_default() -> None:
    """``DeleteDocument`` exposes ``force`` as optional."""

    assert DeleteDocument().force is None
