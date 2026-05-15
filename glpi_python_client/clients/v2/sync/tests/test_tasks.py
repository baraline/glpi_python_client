from __future__ import annotations

from collections.abc import Callable

import pytest

from glpi_python_client import GlpiClient
from glpi_python_client.testing.utils import SearchResponse, make_task_record


def test_search_task_records_returns_full_list_by_default(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()
    requests: list[tuple[str, dict[str, object] | None]] = []
    responses = iter(
        [
            SearchResponse(
                [
                    make_task_record(id=1, tickets_id=100, actiontime=1200),
                    make_task_record(id=2, tickets_id=101, actiontime=1800),
                ],
                status_code=206,
                headers={"Content-Range": "0-1/3"},
            ),
            SearchResponse(
                [make_task_record(id=3, tickets_id=102, actiontime=2400)],
                status_code=200,
                headers={"Content-Range": "2-2/3"},
            ),
        ]
    )

    def fake_get_request(
        endpoint: str,
        params: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> SearchResponse:
        assert skip_entity is False
        requests.append((endpoint, dict(params or {})))
        assert endpoint == "Assistance/Task"
        return next(responses)

    monkeypatch.setattr(client, "_get_request", fake_get_request)
    try:
        tasks = client.search_task_records(
            query="date=ge=2026-01-01;date=le=2026-01-31",
            fields=("content", "actiontime"),
            sort="date:desc",
        )

        assert [task.task_id for task in tasks] == ["1", "2", "3"]
        assert [task.duration for task in tasks] == [1200, 1800, 2400]
        assert tasks[0].ticket_id == "100"
        assert requests[0][1] == {
            "start": 0,
            "filter": "date=ge=2026-01-01;date=le=2026-01-31",
            "fields": (
                "content,actiontime,id,is_private,date,date_creation,date_mod,"
                "users_id,user,user_editor,tickets_id,entity,entities_id"
            ),
            "sort": "date:desc",
        }
        assert [request[1]["start"] for request in requests] == [0, 2]
    finally:
        client.close()


def test_search_task_records_returns_lazy_batches_when_requested(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()
    responses = iter(
        [
            SearchResponse(
                [make_task_record(id=1), make_task_record(id=2)],
                status_code=206,
                headers={"Content-Range": "0-1/3"},
            ),
            SearchResponse(
                [make_task_record(id=3)],
                status_code=200,
                headers={"Content-Range": "2-2/3"},
            ),
        ]
    )

    def fake_get_request(
        endpoint: str,
        params: dict[str, object] | None = None,
        skip_entity: bool = False,
    ) -> SearchResponse:
        assert endpoint == "Assistance/Task"
        assert params is not None
        assert params["limit"] == 2
        return next(responses)

    monkeypatch.setattr(client, "_get_request", fake_get_request)
    try:
        batches = client.search_task_records(batch_size=2)

        assert [[task.task_id for task in batch] for batch in batches] == [
            ["1", "2"],
            ["3"],
        ]
    finally:
        client.close()
