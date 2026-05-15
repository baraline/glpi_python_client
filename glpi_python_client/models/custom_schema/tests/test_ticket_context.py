"""Smoke tests for the custom_schema aggregated views."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from glpi_python_client.models.custom_schema import GlpiTicketContext


def test_ticket_context_requires_ticket() -> None:
    """``GlpiTicketContext`` requires the ``ticket`` field to be present."""

    with pytest.raises(ValidationError):
        GlpiTicketContext.model_validate({})


def test_ticket_context_default_collections_empty() -> None:
    """``GlpiTicketContext`` defaults timeline collections to empty lists."""

    context = GlpiTicketContext.model_validate({"ticket": {"id": 1, "name": "x"}})
    assert context.tasks == []
    assert context.followups == []
    assert context.solutions == []
    assert context.documents == []


def test_ticket_context_accepts_timeline_records() -> None:
    """``GlpiTicketContext`` validates nested timeline payloads."""

    payload = {
        "ticket": {"id": 1, "name": "x"},
        "tasks": [{"id": 11, "content": "<p>do</p>"}],
        "followups": [{"id": 12, "content": "<p>note</p>"}],
        "solutions": [{"id": 13, "content": "<p>fix</p>"}],
        "documents": [{"id": 14, "documents_id": 99}],
    }
    context = GlpiTicketContext.model_validate(payload)
    assert context.tasks[0].id == 11
    assert context.documents[0].documents_id == 99
