"""Unit tests for the asynchronous statistics mixin.

These tests stub :meth:`iter_search_tickets`, :meth:`list_ticket_tasks`,
:meth:`search_entities`, and :meth:`get_task_statistics` directly on an
:class:`AsyncGlpiClient` instance so the async aggregations exercise
their real summarization logic without any HTTP call.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from glpi_python_client import AsyncGlpiClient
from glpi_python_client.models.api_schema._common import (
    IdNameCompletenameRef,
    IdNameRef,
)
from glpi_python_client.models.api_schema.administration._entity import GetEntity
from glpi_python_client.models.api_schema.assistance._ticket import GetTicket
from glpi_python_client.models.api_schema.assistance.timeline._task import (
    GetTicketTask,
)
from glpi_python_client.testing.utils import make_async_client


@pytest.fixture
def aclient() -> AsyncGlpiClient:
    """Return one in-memory asynchronous test client."""

    return make_async_client()


def _make_ticket(ticket_id: int, entity_id: int | None = 1) -> GetTicket:
    """Build a minimal ``GetTicket`` for the duration aggregations."""

    payload: dict[str, Any] = {
        "id": ticket_id,
        "name": f"t{ticket_id}",
        "content": "c",
    }
    if entity_id is not None:
        payload["entity"] = IdNameCompletenameRef(
            id=entity_id, name=f"E{entity_id}", completename=f"E{entity_id}"
        )
    return GetTicket(**payload)


async def _aiter_batches(
    batches: list[list[GetTicket]],
) -> AsyncIterator[list[GetTicket]]:
    """Yield ticket batches as an async iterator (mirrors the bridge wrapper)."""

    for batch in batches:
        yield batch


async def test_async_get_task_durations_empty_iterator(
    aclient: AsyncGlpiClient,
) -> None:
    """An empty ticket iterator returns zeroed totals without task fetches."""

    def fake_iter(
        rsql_filter: str = "", *, batch_size: int = 200
    ) -> AsyncIterator[list[GetTicket]]:
        return _aiter_batches([])

    aclient.iter_search_tickets = fake_iter  # type: ignore[method-assign]
    result = await aclient.get_task_durations(
        start_date="2026-01-01", end_date="2026-01-31"
    )
    assert result["total_duration"] == 0
    assert result["task_count"] == 0
    assert result["duration_by_entity"] == {}
    assert result["tasks"] is None
    await aclient.close()


async def test_async_get_task_durations_entity_grouping(
    aclient: AsyncGlpiClient,
) -> None:
    """``duration_by_entity`` is grouped from the per-ticket statistics."""

    tickets = [_make_ticket(1, entity_id=10), _make_ticket(2, entity_id=20)]

    def fake_iter(
        rsql_filter: str = "", *, batch_size: int = 200
    ) -> AsyncIterator[list[GetTicket]]:
        return _aiter_batches([tickets])

    async def fake_stats(ticket_ids: list[int]) -> dict[str, Any]:
        return {
            "ticket_count": 2,
            "task_count": 2,
            "total_duration": 1200,
            "duration_by_user": {"42": 1200},
            "duration_by_ticket": {1: 600, 2: 600},
        }

    aclient.iter_search_tickets = fake_iter  # type: ignore[method-assign]
    aclient.get_task_statistics = fake_stats  # type: ignore[method-assign]
    result = await aclient.get_task_durations(
        start_date="2026-01-01", end_date="2026-01-31"
    )
    assert result["duration_by_entity"] == {"10": 600, "20": 600}
    assert result["tasks"] is None
    await aclient.close()


async def test_async_get_task_durations_return_task_details(
    aclient: AsyncGlpiClient,
) -> None:
    """``return_task_details=True`` returns a flat task list with metadata."""

    tickets = [_make_ticket(1, entity_id=10)]

    def fake_iter(
        rsql_filter: str = "", *, batch_size: int = 200
    ) -> AsyncIterator[list[GetTicket]]:
        return _aiter_batches([tickets])

    async def fake_stats(ticket_ids: list[int]) -> dict[str, Any]:
        return {
            "ticket_count": 1,
            "task_count": 1,
            "total_duration": 300,
            "duration_by_user": {"7": 300},
            "duration_by_ticket": {1: 300},
        }

    async def fake_list_tasks(ticket_id: int) -> list[GetTicketTask]:
        return [
            GetTicketTask(
                id=99,
                tickets_id=ticket_id,
                duration=300,
                user=IdNameRef(id=7, name="alice"),
            )
        ]

    aclient.iter_search_tickets = fake_iter  # type: ignore[method-assign]
    aclient.get_task_statistics = fake_stats  # type: ignore[method-assign]
    aclient.list_ticket_tasks = fake_list_tasks  # type: ignore[method-assign]
    result = await aclient.get_task_durations(
        start_date="2026-01-01",
        end_date="2026-01-31",
        return_task_details=True,
    )
    tasks = result["tasks"]
    assert isinstance(tasks, list)
    assert len(tasks) == 1
    assert tasks[0]["task_id"] == 99
    assert tasks[0]["ticket_id"] == 1
    assert tasks[0]["duration"] == 300
    assert tasks[0]["user_id"] == 7
    await aclient.close()


async def test_async_get_task_durations_entity_name_no_match(
    aclient: AsyncGlpiClient,
) -> None:
    """When ``entity_name`` matches nothing the helper short-circuits."""

    async def fake_search_entities(
        rsql_filter: str = "", *, limit: int = 50
    ) -> list[GetEntity]:
        return []

    aclient.search_entities = fake_search_entities  # type: ignore[method-assign]
    result = await aclient.get_task_durations(
        start_date="2026-01-01",
        end_date="2026-01-31",
        entity_name="nope",
    )
    assert result["total_duration"] == 0
    assert result["task_count"] == 0
    assert result["duration_by_entity"] == {}
    assert result["tasks"] is None
    await aclient.close()


async def test_async_get_task_durations_entity_name_match(
    aclient: AsyncGlpiClient,
) -> None:
    """When ``entity_name`` matches entities the helper combines RSQL filters."""

    tickets = [_make_ticket(1, entity_id=42)]

    async def fake_search_entities(
        rsql_filter: str = "", *, limit: int = 50
    ) -> list[GetEntity]:
        return [GetEntity(id=42, name="acme", completename="root > acme")]

    captured: dict[str, str] = {}

    def fake_iter(
        rsql_filter: str = "", *, batch_size: int = 200
    ) -> AsyncIterator[list[GetTicket]]:
        captured["filter"] = rsql_filter
        return _aiter_batches([tickets])

    async def fake_stats(ticket_ids: list[int]) -> dict[str, Any]:
        return {
            "ticket_count": 1,
            "task_count": 0,
            "total_duration": 0,
            "duration_by_user": {},
            "duration_by_ticket": {1: 0},
        }

    class _FakeV1:
        """v1 stand-in: ``user_id`` is resolved through the v1 search."""

        def request_json(self, method: str, path: str, **kwargs: Any) -> object:
            return {"totalcount": 1, "data": [{"2": 1}]}

        def close(self) -> None:
            """No-op."""

    aclient.search_entities = fake_search_entities  # type: ignore[method-assign]
    aclient.iter_search_tickets = fake_iter  # type: ignore[method-assign]
    aclient.get_task_statistics = fake_stats  # type: ignore[method-assign]
    aclient._v1 = _FakeV1()  # type: ignore[assignment]

    result = await aclient.get_task_durations(
        start_date="2026-01-01",
        end_date="2026-01-31",
        entity_name="acme",
        user_id=7,
        user_editor_id=8,
        user_recipient_id=9,
        extra_filter="status==1",
    )
    assert result["task_count"] == 0
    assert "entity.id==42" in captured["filter"]
    assert "user_editor.id==8" in captured["filter"]
    assert "user_recipient.id==9" in captured["filter"]
    assert "status==1" in captured["filter"]
    assert "is_deleted==false" in captured["filter"]
    # ``user_id`` selects on actors, which v2 cannot express, so it is
    # resolved through v1 and must not appear in the v2 filter at all.
    assert "users_id_assign" not in captured["filter"]
    assert "user_id" not in captured["filter"]
    # None of the dropped v1 spellings may come back.
    for dead in ("entities_id", "users_id_lastupdater", "users_id_requester"):
        assert dead not in captured["filter"]
    await aclient.close()
