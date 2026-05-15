from __future__ import annotations

from collections.abc import Callable

import pytest

from glpi_python_client import (
    GlpiClient,
    GlpiDocument,
    GlpiEntity,
    GlpiFollowup,
    GlpiPriority,
    GlpiSolution,
    GlpiTask,
    GlpiTeamMember,
    GlpiTicket,
    GlpiTicketStatus,
    GlpiTicketType,
    GlpiUser,
)


def test_ticket_enums_expose_numeric_ids_and_rsql_helpers() -> None:
    assert GlpiTicketStatus.NEW.glpi_id == 1
    assert GlpiPriority.MEDIUM.rsql_equals("priority") == "priority==3"
    assert int(GlpiTicketType.REQUEST) == 2


def test_get_task_durations_applies_default_days_and_returns_details(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()
    observed_queries: list[str | None] = []

    def fake_search_task_records(
        query: str | None = None,
        *,
        fields: tuple[str, ...] = (),
        sort: str | None = None,
        batch_size: int | None = None,
    ) -> list[GlpiTask]:
        observed_queries.append(query)
        assert batch_size is None
        return [
            GlpiTask(task_id="1", ticket_id="100", user_id="7", duration=3600),
            GlpiTask(task_id="2", ticket_id="101", user_id="8", duration=1800),
        ]

    def fake_get_ticket_record(ticket_id: str | int) -> GlpiTicket:
        mapping = {
            "100": GlpiTicket(id="100", entity={"id": 1, "name": "Novahe"}),
            "101": GlpiTicket(id="101", entity={"id": 2, "name": "Other"}),
        }
        return mapping[str(ticket_id)]

    monkeypatch.setattr(client, "search_task_records", fake_search_task_records)
    monkeypatch.setattr(client, "get_ticket_record", fake_get_ticket_record)
    try:
        result = client.get_task_durations(
            end_date="2026-01-31",
            default_days=30,
            return_task_details=True,
        )

        assert observed_queries == ["date=ge=2026-01-02;date=le=2026-01-31"]
        assert result["start_date"] == "2026-01-02"
        assert result["end_date"] == "2026-01-31"
        assert result["total_duration"] == 5400
        assert result["task_count"] == 2
        assert result["duration_by_user"] == {"7": 3600, "8": 1800}
        assert result["duration_by_entity"] == {"Novahe": 3600, "Other": 1800}
        assert [task.task_id for task in result["tasks"]] == ["1", "2"]
    finally:
        client.close()


def test_get_task_durations_filters_by_entity_and_user(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()

    monkeypatch.setattr(
        client,
        "search_entities",
        lambda rsql_filter="", limit=50, start=0: [
            GlpiEntity(entity_id="1", name="Novahe", complete_name="Root > Novahe")
        ],
    )
    monkeypatch.setattr(
        client,
        "search_users",
        lambda rsql_filter="", limit=1, start=0, skip_entity=False: [
            GlpiUser(user_id="7", name="jdoe")
        ],
    )
    monkeypatch.setattr(
        client,
        "search_task_records",
        lambda query=None, fields=(), sort=None, batch_size=None: [
            GlpiTask(task_id="1", ticket_id="100", user_id="7", duration=3600),
            GlpiTask(task_id="2", ticket_id="101", user_id="8", duration=1800),
        ],
    )
    monkeypatch.setattr(
        client,
        "get_ticket_record",
        lambda ticket_id: GlpiTicket(
            id=str(ticket_id),
            entity={
                "id": 1 if str(ticket_id) == "100" else 2,
                "name": "Novahe" if str(ticket_id) == "100" else "Other",
            },
        ),
    )
    try:
        result = client.get_task_durations(
            start_date="2026-01-01",
            end_date="2026-01-31",
            entity_name="Novahe",
            name="jdoe",
        )

        assert result["total_duration"] == 3600
        assert result["task_count"] == 1
        assert result["duration_by_user"] == {"jdoe": 3600}
        assert result["duration_by_entity"] == {"Root > Novahe": 3600}
    finally:
        client.close()


def test_get_ticket_statistics_groups_counts_by_entity_status_priority_and_type(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()

    def fake_search_ticket_records(
        query=None,
        fields=(),
        sort=None,
        batch_size=None,
        include_deleted_ticket=False,
    ) -> list[GlpiTicket]:
        _ = (query, fields, sort, batch_size, include_deleted_ticket)
        return [
            GlpiTicket(
                id="1",
                entity={"id": 1, "name": "Novahe"},
                status=1,
                priority=3,
                type=1,
            ),
            GlpiTicket(
                id="2",
                entity={"id": 1, "name": "Novahe"},
                status=2,
                priority=3,
                type=2,
            ),
        ]

    monkeypatch.setattr(
        client,
        "search_ticket_records",
        fake_search_ticket_records,
    )
    try:
        result = client.get_ticket_statistics(
            start_date="2026-01-01",
            end_date="2026-01-31",
        )

        assert result == {
            "entities": {
                "Novahe": {
                    "total": 2,
                    "by_status": {"NEW": 1, "ASSIGNED": 1},
                    "by_priority": {"MEDIUM": 2},
                    "by_type": {"INCIDENT": 1, "REQUEST": 1},
                }
            }
        }
    finally:
        client.close()


def test_get_user_activity_counts_requester_and_team_assignments(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()

    def fake_search_ticket_records(
        query=None,
        fields=(),
        sort=None,
        batch_size=None,
        include_deleted_ticket=False,
    ) -> list[GlpiTicket]:
        _ = (query, fields, sort, batch_size, include_deleted_ticket)
        return [
            GlpiTicket(id="100", user_recipient=GlpiUser(user_id="7")),
            GlpiTicket(id="101", user_recipient=GlpiUser(user_id="9")),
        ]

    monkeypatch.setattr(
        client,
        "search_users",
        lambda rsql_filter="", limit=1, start=0, skip_entity=False: [
            GlpiUser(user_id="7", name="jdoe")
        ],
    )
    monkeypatch.setattr(
        client,
        "search_ticket_records",
        fake_search_ticket_records,
    )
    monkeypatch.setattr(
        client,
        "get_team_member_records",
        lambda ticket_id: (
            [GlpiTeamMember(member_type="User", member_id=7, role="1")]
            if str(ticket_id) == "101"
            else []
        ),
    )
    monkeypatch.setattr(
        client,
        "get_task_durations",
        lambda **kwargs: {
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "total_duration": 3600,
            "task_count": 1,
            "duration_by_user": {"jdoe": 3600},
            "duration_by_entity": {"Novahe": 3600},
        },
    )
    try:
        result = client.get_user_activity(
            name="jdoe",
            start_date="2026-01-01",
            end_date="2026-01-31",
        )

        assert result == {
            "users": {
                "jdoe": {
                    "user_ids": [7],
                    "tickets_as_technician": 1,
                    "tickets_as_recipient": 1,
                    "task_durations": {
                        "start_date": "2026-01-01",
                        "end_date": "2026-01-31",
                        "total_duration": 3600,
                        "task_count": 1,
                        "duration_by_user": {"jdoe": 3600},
                        "duration_by_entity": {"Novahe": 3600},
                    },
                }
            }
        }
    finally:
        client.close()


def test_get_user_activity_requires_one_identifier(
    client_factory: Callable[..., GlpiClient],
) -> None:
    client = client_factory()
    try:
        with pytest.raises(ValueError, match="requires at least one user identifier"):
            client.get_user_activity()
    finally:
        client.close()


def test_get_ticket_context_groups_existing_public_record_helpers(
    client_factory: Callable[..., GlpiClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_factory()

    monkeypatch.setattr(
        client, "get_ticket_record", lambda ticket_id: GlpiTicket(id="321")
    )
    monkeypatch.setattr(
        client, "get_task_records", lambda ticket_id: [GlpiTask(task_id="1")]
    )
    monkeypatch.setattr(
        client,
        "get_followup_records",
        lambda ticket_id: [GlpiFollowup(followup_id="2")],
    )
    monkeypatch.setattr(
        client,
        "get_solution_records",
        lambda ticket_id: [GlpiSolution(solution_id="3")],
    )
    monkeypatch.setattr(
        client,
        "get_document_records",
        lambda ticket_id: [GlpiDocument(document_id="4")],
    )
    try:
        context = client.get_ticket_context("321")

        assert context.ticket.id == "321"
        assert [task.task_id for task in context.tasks] == ["1"]
        assert [followup.followup_id for followup in context.followups] == ["2"]
        assert [solution.solution_id for solution in context.solutions] == ["3"]
        assert [document.document_id for document in context.documents] == ["4"]
    finally:
        client.close()
