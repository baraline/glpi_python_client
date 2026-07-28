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
    GlpiValidationError,
)
from glpi_python_client._sync.clients.custom._statistics import (
    _V1_SO_ASSIGNEE,
    _V1_SO_REQUESTER,
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


class _FakeV1Search:
    """Stand-in v1 session answering ``search/Ticket`` actor lookups.

    Maps a v1 searchOption id to the ticket ids that option should match,
    and mimics the wire shape the real endpoint returns: rows keyed by the
    searchOption id as a *string*, plus a ``totalcount`` used to bound
    paging (the live API answers HTTP 400 for a range past the end).
    """

    def __init__(self, by_option: dict[int, list[int]]) -> None:
        self.by_option = by_option
        self.calls: list[dict[str, Any]] = []

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, object] | None = None,
        json_body: dict[str, object] | None = None,
        success_statuses: tuple[int, ...] = (200, 201, 204, 206),
        failure_message: str | None = None,
    ) -> object:
        self.calls.append({"method": method, "path": path, "params": params})
        criteria = params or {}
        matched: list[int] = []
        index = 0
        while f"criteria[{index}][field]" in criteria:
            option = int(str(criteria[f"criteria[{index}][field]"]))
            matched.extend(self.by_option.get(option, []))
            index += 1
        rows = [{"2": ticket_id} for ticket_id in sorted(set(matched))]
        return {"totalcount": len(rows), "data": rows}


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


def test_get_ticket_statistics_aggregates_by_entity_status_priority_type(
    client: GlpiClient,
) -> None:
    """All aggregation buckets are produced from the search response."""

    captured: dict[str, Any] = {}

    def fake_search(
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
    result = client.get_ticket_statistics(
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


def test_get_ticket_statistics_default_window_uses_today(
    client: GlpiClient,
) -> None:
    """When no dates are passed the helper uses today minus default_days."""

    captured: dict[str, Any] = {}

    def fake_search(
        rsql_filter: str = "", *, limit: int = 50, start: int = 0
    ) -> list[GetTicket]:
        captured["filter"] = rsql_filter
        return []

    client.search_tickets = fake_search  # type: ignore[method-assign]
    client.get_ticket_statistics(default_days=7)
    end = date.today()
    start = end - timedelta(days=6)
    assert f"date_creation=ge={start.isoformat()}" in captured["filter"]
    assert f"date_creation=le={end.isoformat()} 23:59:59" in captured["filter"]


def test_get_ticket_statistics_rejects_invalid_window(client: GlpiClient) -> None:
    """Invalid date inputs raise locally before any HTTP request.

    ``GlpiValidationError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working.
    """

    with pytest.raises(GlpiValidationError, match="default_days") as exc1:
        client.get_ticket_statistics(default_days=0)
    assert isinstance(exc1.value, ValueError)
    with pytest.raises(GlpiValidationError, match="start_date") as exc2:
        client.get_ticket_statistics(start_date="2026-02-01", end_date="2026-01-01")
    assert isinstance(exc2.value, ValueError)


def test_get_ticket_statistics_rejects_malformed_iso_date(
    client: GlpiClient,
) -> None:
    """A malformed ISO date string raises ``GlpiValidationError``, not a bare
    ``date.fromisoformat`` ``ValueError``.

    ``GlpiValidationError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working, and the original ``ValueError``
    from ``date.fromisoformat`` is chained via ``from`` rather than
    swallowed.
    """

    with pytest.raises(GlpiValidationError, match="start_date") as excinfo:
        client.get_ticket_statistics(start_date="2026-13-45", end_date="2026-01-31")
    assert isinstance(excinfo.value, ValueError)
    assert isinstance(excinfo.value.__cause__, ValueError)


def test_get_task_statistics_zero_for_empty_input(client: GlpiClient) -> None:
    """An empty ticket list returns zeroed totals without any HTTP call."""

    result = client.get_task_statistics([])
    assert result == {
        "ticket_count": 0,
        "task_count": 0,
        "total_duration": 0,
        "duration_by_user": {},
        "duration_by_ticket": {},
    }


def test_get_task_statistics_aggregates_by_user_and_ticket(
    client: GlpiClient,
) -> None:
    """Durations group by user and parent ticket."""

    def fake_list(ticket_id: int) -> list[GetTicketTask]:
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
    result = client.get_task_statistics([1, 2])
    assert result["ticket_count"] == 2
    assert result["task_count"] == 3
    assert result["total_duration"] == 900
    assert result["duration_by_user"] == {"42": 600, "unknown": 300}
    assert result["duration_by_ticket"] == {1: 900}


# ---------------------------------------------------------------------------
# get_ticket_statistics — extended filters (Change 2)
# ---------------------------------------------------------------------------


def test_get_ticket_statistics_entity_id_filter(client: GlpiClient) -> None:
    """When entity_id is given its RSQL clause is appended to the filter."""

    captured: dict[str, Any] = {}

    def fake_search(
        rsql_filter: str = "", *, limit: int = 50, start: int = 0
    ) -> list[GetTicket]:
        captured["filter"] = rsql_filter
        return []

    client.search_tickets = fake_search  # type: ignore[method-assign]
    client.get_ticket_statistics(
        start_date="2026-01-01",
        end_date="2026-01-31",
        entity_id=7,
    )
    # v2 types Ticket.entity as object{id,name}; the bare `entities_id` is a
    # v1 field name that v2 silently ignores, returning every ticket.
    assert "entity.id==7" in captured["filter"]
    assert "entities_id" not in captured["filter"]
    # v2 counts soft-deleted tickets unless told otherwise.
    assert "is_deleted==false" in captured["filter"]


def test_get_ticket_statistics_entity_name_resolution(client: GlpiClient) -> None:
    """When entity_name is given entities are resolved and IDs ORed."""

    from glpi_python_client.models.api_schema.administration._entity import GetEntity

    captured_tickets: dict[str, Any] = {}

    def fake_search_entities(
        rsql_filter: str = "", *, limit: int | None = 200, start: int = 0
    ) -> list[GetEntity]:
        return [GetEntity(id=3, name="Acme"), GetEntity(id=4, name="Acme Sub")]

    def fake_search(
        rsql_filter: str = "", *, limit: int = 50, start: int = 0
    ) -> list[GetTicket]:
        captured_tickets["filter"] = rsql_filter
        return []

    client.search_entities = fake_search_entities  # type: ignore[method-assign]
    client.search_tickets = fake_search  # type: ignore[method-assign]
    client.get_ticket_statistics(
        start_date="2026-01-01",
        end_date="2026-01-31",
        entity_name="Acme",
    )
    assert "entity.id==3" in captured_tickets["filter"]
    assert "entity.id==4" in captured_tickets["filter"]
    assert "entities_id" not in captured_tickets["filter"]
    # The OR group must be parenthesised or the date window stops applying
    # to every entity after the first.
    assert "(entity.id==3,entity.id==4)" in captured_tickets["filter"]


def test_get_ticket_statistics_entity_name_no_match(client: GlpiClient) -> None:
    """When entity_name matches nothing the fast-path returns empty entities."""

    from glpi_python_client.models.api_schema.administration._entity import GetEntity

    def fake_search_entities(
        rsql_filter: str = "", *, limit: int | None = 200, start: int = 0
    ) -> list[GetEntity]:
        return []

    client.search_entities = fake_search_entities  # type: ignore[method-assign]
    result = client.get_ticket_statistics(
        start_date="2026-01-01",
        end_date="2026-01-31",
        entity_name="NonExistent",
    )
    assert result == {"entities": {}}


def test_get_ticket_statistics_extra_filter_appended(client: GlpiClient) -> None:
    """extra_filter is AND-joined with the date window."""

    captured: dict[str, Any] = {}

    def fake_search(
        rsql_filter: str = "", *, limit: int = 50, start: int = 0
    ) -> list[GetTicket]:
        captured["filter"] = rsql_filter
        return []

    client.search_tickets = fake_search  # type: ignore[method-assign]
    client.get_ticket_statistics(
        start_date="2026-01-01",
        end_date="2026-01-31",
        extra_filter="priority==5",
    )
    assert "date_creation=ge=2026-01-01" in captured["filter"]
    assert "priority==5" in captured["filter"]


def test_get_ticket_statistics_default_days_window(client: GlpiClient) -> None:
    """default_days shifts the start of the window without other params."""

    from datetime import date, timedelta

    captured: dict[str, Any] = {}

    def fake_search(
        rsql_filter: str = "", *, limit: int = 50, start: int = 0
    ) -> list[GetTicket]:
        captured["filter"] = rsql_filter
        return []

    client.search_tickets = fake_search  # type: ignore[method-assign]
    client.get_ticket_statistics(default_days=14)
    end = date.today()
    start = end - timedelta(days=13)
    assert f"date_creation=ge={start.isoformat()}" in captured["filter"]
    assert f"date_creation=le={end.isoformat()} 23:59:59" in captured["filter"]


# ---------------------------------------------------------------------------
# get_task_durations (Change 3)
# ---------------------------------------------------------------------------


def _make_ticket(ticket_id: int, entity_id: int | None = 1) -> GetTicket:
    """Build a minimal GetTicket for task-duration tests."""

    payload: dict[str, Any] = {"id": ticket_id, "name": f"t{ticket_id}", "content": "c"}
    if entity_id is not None:
        payload["entity"] = IdNameCompletenameRef(
            id=entity_id, name=f"E{entity_id}", completename=f"E{entity_id}"
        )
    return GetTicket(**payload)


def test_get_task_durations_empty_ticket_list(client: GlpiClient) -> None:
    """When no tickets match, all durations are zero."""

    def fake_iter(rsql_filter: str = "", *, batch_size: int = 200):
        return iter([])

    client.iter_search_tickets = fake_iter  # type: ignore[method-assign]
    result = client.get_task_durations(start_date="2026-01-01", end_date="2026-01-31")
    assert result["total_duration"] == 0
    assert result["task_count"] == 0
    assert result["duration_by_entity"] == {}
    assert result["tasks"] is None


def test_get_task_durations_entity_grouping(client: GlpiClient) -> None:
    """duration_by_entity groups ticket-task durations by entity key."""

    tickets = [_make_ticket(1, entity_id=10), _make_ticket(2, entity_id=20)]

    def fake_iter(rsql_filter: str = "", *, batch_size: int = 200):
        yield tickets

    def fake_task_stats(ticket_ids: list[int]) -> dict[str, Any]:
        return {
            "ticket_count": 2,
            "task_count": 2,
            "total_duration": 1200,
            "duration_by_user": {"42": 1200},
            "duration_by_ticket": {1: 600, 2: 600},
        }

    client.iter_search_tickets = fake_iter  # type: ignore[method-assign]
    client.get_task_statistics = fake_task_stats  # type: ignore[method-assign]
    result = client.get_task_durations(start_date="2026-01-01", end_date="2026-01-31")
    assert result["duration_by_entity"] == {"10": 600, "20": 600}


def test_get_task_durations_return_task_details_true(client: GlpiClient) -> None:
    """When return_task_details=True a tasks list with correct shape is returned."""

    tickets = [_make_ticket(1, entity_id=10)]

    def fake_iter(rsql_filter: str = "", *, batch_size: int = 200):
        yield tickets

    def fake_task_stats(ticket_ids: list[int]) -> dict[str, Any]:
        return {
            "ticket_count": 1,
            "task_count": 1,
            "total_duration": 300,
            "duration_by_user": {"7": 300},
            "duration_by_ticket": {1: 300},
        }

    def fake_list_tasks(ticket_id: int) -> list[GetTicketTask]:
        return [
            GetTicketTask(
                id=99,
                tickets_id=ticket_id,
                duration=300,
                user=IdNameRef(id=7, name="alice"),
            )
        ]

    client.iter_search_tickets = fake_iter  # type: ignore[method-assign]
    client.get_task_statistics = fake_task_stats  # type: ignore[method-assign]
    client.list_ticket_tasks = fake_list_tasks  # type: ignore[method-assign]
    result = client.get_task_durations(
        start_date="2026-01-01", end_date="2026-01-31", return_task_details=True
    )
    assert isinstance(result["tasks"], list)
    assert len(result["tasks"]) == 1
    task = result["tasks"][0]
    assert task["task_id"] == 99
    assert task["ticket_id"] == 1
    assert task["duration"] == 300
    assert task["user_id"] == 7


def test_get_task_durations_return_task_details_false(client: GlpiClient) -> None:
    """When return_task_details=False the tasks key is None."""

    def fake_iter(rsql_filter: str = "", *, batch_size: int = 200):
        return iter([])

    client.iter_search_tickets = fake_iter  # type: ignore[method-assign]
    result = client.get_task_durations(start_date="2026-01-01", end_date="2026-01-31")
    assert result["tasks"] is None


# ---------------------------------------------------------------------------
# get_user_activity (Change 4)
# ---------------------------------------------------------------------------


def test_get_user_activity_raises_without_identifier(client: GlpiClient) -> None:
    """Calling without any identifier raises ``GlpiValidationError``.

    ``GlpiValidationError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working.
    """

    with pytest.raises(GlpiValidationError, match="user_id") as excinfo:
        client.get_user_activity()
    assert isinstance(excinfo.value, ValueError)


def test_get_user_activity_single_user_happy_path(client: GlpiClient) -> None:
    """A single matched user populates all activity keys."""

    from glpi_python_client.models.api_schema.administration._user import GetUser

    def fake_search_users(
        rsql_filter: str = "",
        *,
        limit: int = 200,
        start: int = 0,
        skip_entity: bool = False,
    ) -> list[GetUser]:
        return [GetUser(id=42, username="alice", firstname="Alice", realname="Smith")]

    window_calls: list[str] = []

    def fake_iter(rsql_filter: str = "", *, batch_size: int = 200):
        # One date-window walk now serves every user and every role; the
        # per-role split comes from the v1 id sets intersected below.
        window_calls.append(rsql_filter)
        yield [_make_ticket(1), _make_ticket(2)]

    # Ticket 1 is assigned to the user, ticket 2 is not; ticket 3 is
    # assigned but falls outside the window, so it must not be counted.
    client._v1 = _FakeV1Search(  # type: ignore[assignment]
        {_V1_SO_ASSIGNEE: [1, 3], _V1_SO_REQUESTER: []}
    )

    def fake_task_durations(
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        default_days: int = 30,
        user_id: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "total_duration": 600,
            "task_count": 1,
            "duration_by_user": {"42": 600},
            "duration_by_entity": {"10": 600},
        }

    client.search_users = fake_search_users  # type: ignore[method-assign]
    client.iter_search_tickets = fake_iter  # type: ignore[method-assign]
    client.get_task_durations = fake_task_durations  # type: ignore[method-assign]

    result = client.get_user_activity(
        username="alice", start_date="2026-01-01", end_date="2026-01-31"
    )
    users = result["users"]
    assert len(users) == 1
    key = next(iter(users))
    data = users[key]
    assert data["user_ids"] == [42]
    # Ticket 1 is both in the window and assigned; ticket 3 is assigned but
    # outside the window, so the intersection keeps exactly one.
    assert data["tickets_as_technician"] == 1
    assert data["tickets_as_recipient"] == 0
    assert "total_duration" in data["task_durations"]
    # The window is walked once, not once per user per role, and it must
    # exclude trashed tickets.
    assert len(window_calls) == 1
    assert "is_deleted==false" in window_calls[0]
    # A regression to the v1 field names would be invisible against the
    # live server, so pin their absence here.
    assert "users_id_assign" not in window_calls[0]
    assert "users_id_requester" not in window_calls[0]


def test_get_user_activity_raises_when_no_users_matched(client: GlpiClient) -> None:
    """When search_users returns empty a ``GlpiValidationError`` is raised.

    ``GlpiValidationError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working.
    """

    from glpi_python_client.models.api_schema.administration._user import GetUser

    def fake_search_users(
        rsql_filter: str = "",
        *,
        limit: int = 200,
        start: int = 0,
        skip_entity: bool = False,
    ) -> list[GetUser]:
        return []

    client.search_users = fake_search_users  # type: ignore[method-assign]
    with pytest.raises(GlpiValidationError, match="No users matched") as excinfo:
        client.get_user_activity(username="ghost")
    assert isinstance(excinfo.value, ValueError)


def test_get_user_activity_multi_user_merge(client: GlpiClient) -> None:
    """Multiple users under the same display key have their counts merged."""

    from glpi_python_client.models.api_schema.administration._user import GetUser

    def fake_search_users(
        rsql_filter: str = "",
        *,
        limit: int = 200,
        start: int = 0,
        skip_entity: bool = False,
    ) -> list[GetUser]:
        return [
            GetUser(id=1, username="a1", firstname="Alice", realname="Smith"),
            GetUser(id=2, username="a2", firstname="Alice", realname="Smith"),
        ]

    def fake_iter(rsql_filter: str = "", *, batch_size: int = 200):
        yield [_make_ticket(1)]

    # Both merged users are assigned ticket 1, so each contributes 1.
    client._v1 = _FakeV1Search(  # type: ignore[assignment]
        {_V1_SO_ASSIGNEE: [1], _V1_SO_REQUESTER: []}
    )

    def fake_task_durations(
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        default_days: int = 30,
        user_id: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "total_duration": 300,
            "task_count": 1,
            "duration_by_user": {str(user_id): 300},
            "duration_by_entity": {"10": 300},
        }

    client.search_users = fake_search_users  # type: ignore[method-assign]
    client.iter_search_tickets = fake_iter  # type: ignore[method-assign]
    client.get_task_durations = fake_task_durations  # type: ignore[method-assign]

    result = client.get_user_activity(
        realname="Smith", start_date="2026-01-01", end_date="2026-01-31"
    )
    users = result["users"]
    # Both users share the same display key → merged into one entry
    assert len(users) == 1
    key = next(iter(users))
    data = users[key]
    assert sorted(data["user_ids"]) == [1, 2]
    assert data["tickets_as_technician"] == 2  # 1 per user
    assert data["task_durations"]["total_duration"] == 600  # 300 per user


class _FakeV1Tasks:
    """v1 stand-in serving pages of raw ``TicketTask`` collection rows."""

    def __init__(self, rows: list[dict[str, Any]], page_size: int = 1000) -> None:
        self.rows = rows
        self.page_size = page_size
        self.calls: list[dict[str, Any]] = []

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, object] | None = None,
        json_body: dict[str, object] | None = None,
        success_statuses: tuple[int, ...] = (200, 201, 204, 206),
        failure_message: str | None = None,
    ) -> object:
        self.calls.append({"path": path, "params": params})
        rng = str((params or {}).get("range", "0-999"))
        start = int(rng.split("-")[0])
        return self.rows[start : start + self.page_size]

    def close(self) -> None:
        """No-op."""


def _task_row(
    task_id: int, ticket_id: int, duration: int, author: int
) -> dict[str, Any]:
    return {
        "id": task_id,
        "tickets_id": ticket_id,
        "actiontime": duration,
        "users_id": author,
        "users_id_tech": 999,
        "date_creation": "2026-07-10 09:00:00",
    }


def test_v1_task_statistics_matches_the_per_ticket_shape(client: GlpiClient) -> None:
    """The bulk v1 sweep produces the same aggregate as the per-ticket path.

    v1 ``actiontime`` is v2 ``duration`` and v1 ``users_id`` is the v2 task
    ``user``; both were confirmed equal against a live GLPI 11 instance, so
    the optimisation must not change any returned value.
    """

    rows = [
        _task_row(1, 10, 600, 5),
        _task_row(2, 10, 300, 5),
        _task_row(3, 11, 900, 7),
        # Belongs to a ticket outside the requested set and must be ignored.
        _task_row(4, 99, 12345, 5),
    ]
    client._v1 = _FakeV1Tasks(rows)  # type: ignore[assignment]

    result = client._v1_task_statistics([10, 11], since=date(2026, 7, 1))

    assert result["ticket_count"] == 2
    assert result["task_count"] == 3
    assert result["total_duration"] == 1800
    assert result["duration_by_ticket"] == {10: 900, 11: 900}
    assert result["duration_by_user"] == {"5": 900, "7": 900}


def test_v1_task_statistics_stops_paging_before_the_window(
    client: GlpiClient,
) -> None:
    """Paging stops once a page predates the window start.

    A task cannot exist before its ticket, so nothing relevant is skipped.
    """

    old = _task_row(5, 10, 60, 5) | {"date_creation": "2020-01-01 09:00:00"}
    fake = _FakeV1Tasks([_task_row(1, 10, 600, 5), old], page_size=2)
    client._v1 = fake  # type: ignore[assignment]

    result = client._v1_task_statistics([10], since=date(2026, 7, 1))

    # Both rows are in the first page, so they are both aggregated; the
    # sweep then stops rather than requesting another page.
    assert result["task_count"] == 2
    assert len(fake.calls) == 1
    assert fake.calls[0]["path"] == "TicketTask"
    assert fake.calls[0]["params"]["sort"] == "date_creation"
    assert fake.calls[0]["params"]["order"] == "DESC"


def test_get_task_durations_uses_per_ticket_path_below_threshold(
    client: GlpiClient,
) -> None:
    """A small ticket set keeps the v2 per-ticket path and needs no v1."""

    def fake_iter(rsql_filter: str = "", *, batch_size: int = 200):
        yield [_make_ticket(1)]

    calls: list[list[int]] = []

    def fake_task_stats(ticket_ids: list[int]) -> dict[str, Any]:
        calls.append(ticket_ids)
        return {
            "ticket_count": len(ticket_ids),
            "task_count": 0,
            "total_duration": 0,
            "duration_by_user": {},
            "duration_by_ticket": {},
        }

    client.iter_search_tickets = fake_iter  # type: ignore[method-assign]
    client.get_task_statistics = fake_task_stats  # type: ignore[method-assign]
    # No v1 session configured at all: the small-set path must not need one.
    result = client.get_task_durations(start_date="2026-07-01", end_date="2026-07-31")

    assert result["task_count"] == 0
    assert calls == [[1]]
