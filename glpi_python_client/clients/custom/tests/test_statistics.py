"""Unit tests for the asynchronous statistics helpers.

The tests stub the API methods on a real :class:`GlpiClient` so the
statistics aggregations exercise their real summarization logic without any
network call.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from glpi_python_client import (
    GlpiClient,
    GlpiPriority,
    GlpiTicketStatus,
    GlpiTicketType,
)
from glpi_python_client.models.api_schema._common import (
    IdNameCompletenameRef,
    IdNameRef,
)
from glpi_python_client.models.api_schema.assistance._ticket import GetTicket
from glpi_python_client.models.api_schema.assistance.timeline._task import (
    GetTicketTask,
)
from glpi_python_client.testing.utils import make_client


@pytest.fixture
def client() -> GlpiClient:
    """Return one in-memory test client."""

    return make_client()


def _ticket(
    *,
    entity_id: int | None = 1,
    status_id: int | None = GlpiTicketStatus.NEW.value,
    priority: int | None = GlpiPriority.MEDIUM.value,
    ticket_type: int | None = GlpiTicketType.INCIDENT.value,
) -> GetTicket:
    """Build one validated ticket model with the requested aggregation keys."""

    payload: dict[str, Any] = {
        "id": 1,
        "name": "demo",
        "content": "<p>x</p>",
    }
    if entity_id is not None:
        payload["entity"] = IdNameCompletenameRef(
            id=entity_id, name=f"E{entity_id}", completename=f"E{entity_id}"
        )
    if status_id is not None:
        payload["status"] = IdNameRef(id=status_id, name=f"s{status_id}")
    if priority is not None:
        payload["priority"] = priority
    if ticket_type is not None:
        payload["type"] = ticket_type
    return GetTicket(**payload)


async def test_get_ticket_statistics_aggregates_by_entity_status_priority_type(
    client: GlpiClient,
) -> None:
    """All aggregation buckets are produced from the search response."""

    captured: dict[str, Any] = {}

    async def fake_search(
        rsql_filter: str = "", *, limit: int = 50, start: int = 0
    ) -> list[GetTicket]:
        captured["filter"] = rsql_filter
        return [
            _ticket(),
            _ticket(
                entity_id=1,
                status_id=GlpiTicketStatus.SOLVED.value,
                priority=GlpiPriority.HIGH.value,
                ticket_type=GlpiTicketType.REQUEST.value,
            ),
            _ticket(
                entity_id=2,
                status_id=GlpiTicketStatus.NEW.value,
                priority=GlpiPriority.LOW.value,
                ticket_type=None,
            ),
            _ticket(entity_id=None, status_id=None, priority=None, ticket_type=None),
        ]

    client.search_tickets = fake_search  # type: ignore[method-assign]
    result = await client.get_ticket_statistics(
        start_date="2026-01-01",
        end_date="2026-01-31",
        extra_filter="status==1",
    )

    assert "date_creation=ge=2026-01-01" in captured["filter"]
    assert "status==1" in captured["filter"]

    entities = result["entities"]
    assert "1" in entities and "2" in entities and "unknown" in entities
    assert entities["1"]["total"] == 2
    assert entities["1"]["by_priority"] == {"MEDIUM": 1, "HIGH": 1}
    assert entities["1"]["by_type"] == {"INCIDENT": 1, "REQUEST": 1}
    # Unknown entity bucket falls back to UNKNOWN labels for missing fields.
    assert entities["unknown"]["by_type"] == {"UNKNOWN": 1}
    assert entities["unknown"]["by_priority"] == {"UNKNOWN": 1}
    assert entities["unknown"]["by_status"] == {"UNKNOWN": 1}


async def test_get_ticket_statistics_default_window_uses_today(
    client: GlpiClient,
) -> None:
    """When no dates are passed the helper uses today minus default_days."""

    captured: dict[str, Any] = {}

    async def fake_search(
        rsql_filter: str = "", *, limit: int = 50, start: int = 0
    ) -> list[GetTicket]:
        captured["filter"] = rsql_filter
        return []

    client.search_tickets = fake_search  # type: ignore[method-assign]
    await client.get_ticket_statistics(default_days=7)
    end = date.today()
    start = end - timedelta(days=6)
    assert f"date_creation=ge={start.isoformat()}" in captured["filter"]
    assert f"date_creation=le={end.isoformat()}" in captured["filter"]


async def test_get_ticket_statistics_rejects_invalid_window(client: GlpiClient) -> None:
    """Invalid date inputs raise locally before any HTTP request."""

    with pytest.raises(ValueError, match="default_days"):
        await client.get_ticket_statistics(default_days=0)
    with pytest.raises(ValueError, match="start_date"):
        await client.get_ticket_statistics(
            start_date="2026-02-01", end_date="2026-01-01"
        )


async def test_get_task_statistics_zero_for_empty_input(client: GlpiClient) -> None:
    """An empty ticket list returns zeroed totals without any HTTP call."""

    result = await client.get_task_statistics([])
    assert result == {
        "ticket_count": 0,
        "task_count": 0,
        "total_duration": 0,
        "duration_by_user": {},
        "duration_by_ticket": {},
    }


async def test_get_task_statistics_aggregates_by_user_and_ticket(
    client: GlpiClient,
) -> None:
    """Durations group by user and parent ticket."""

    async def fake_list(ticket_id: int) -> list[GetTicketTask]:
        if ticket_id == 1:
            return [
                GetTicketTask(
                    id=10,
                    tickets_id=1,
                    duration=600,
                    user=IdNameRef(id=42, name="alice"),
                ),
                GetTicketTask(
                    id=11,
                    tickets_id=1,
                    duration=300,
                    user=None,
                ),
            ]
        return [
            GetTicketTask(
                id=20,
                tickets_id=None,
                duration=None,
                user=IdNameRef(id=42, name="alice"),
            ),
        ]

    client.list_ticket_tasks = fake_list  # type: ignore[method-assign]
    result = await client.get_task_statistics([1, 2])
    assert result["ticket_count"] == 2
    assert result["task_count"] == 3
    assert result["total_duration"] == 900
    assert result["duration_by_user"] == {"42": 600, "unknown": 300}
    assert result["duration_by_ticket"] == {1: 900}
