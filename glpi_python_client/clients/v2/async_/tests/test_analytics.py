from __future__ import annotations

import asyncio

import pytest

from glpi_python_client import (
    AsyncGlpiClient,
    GlpiDocument,
    GlpiEntity,
    GlpiFollowup,
    GlpiSolution,
    GlpiTask,
    GlpiTeamMember,
    GlpiTicket,
    GlpiUser,
)


def test_async_get_task_durations_filters_by_entity_and_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_test() -> None:
        client = AsyncGlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/",
            client_id="client-id",
            client_secret="client-secret",
        )

        async def fake_search_entities(rsql_filter="", limit=50, start=0):
            return [
                GlpiEntity(
                    entity_id="1",
                    name="Novahe",
                    complete_name="Root > Novahe",
                )
            ]

        async def fake_search_users(
            rsql_filter="", limit=1, start=0, skip_entity=False
        ):
            return [GlpiUser(user_id="7", name="jdoe")]

        async def fake_search_task_records(
            query=None, fields=(), sort=None, batch_size=None
        ):
            return [
                GlpiTask(task_id="1", ticket_id="100", user_id="7", duration=3600),
                GlpiTask(task_id="2", ticket_id="101", user_id="8", duration=1800),
            ]

        async def fake_get_ticket_record(ticket_id):
            return GlpiTicket(
                id=str(ticket_id),
                entity={
                    "id": 1 if str(ticket_id) == "100" else 2,
                    "name": "Novahe" if str(ticket_id) == "100" else "Other",
                },
            )

        monkeypatch.setattr(client, "search_entities", fake_search_entities)
        monkeypatch.setattr(client, "search_users", fake_search_users)
        monkeypatch.setattr(client, "search_task_records", fake_search_task_records)
        monkeypatch.setattr(client, "get_ticket_record", fake_get_ticket_record)
        try:
            result = await client.get_task_durations(
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
            await client.close()

    asyncio.run(run_test())


def test_async_get_ticket_statistics_groups_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_test() -> None:
        client = AsyncGlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/",
            client_id="client-id",
            client_secret="client-secret",
        )

        async def fake_search_ticket_records(
            query=None,
            fields=(),
            sort=None,
            batch_size=None,
            include_deleted_ticket=False,
        ):
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

        monkeypatch.setattr(client, "search_ticket_records", fake_search_ticket_records)
        try:
            result = await client.get_ticket_statistics(
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
            await client.close()

    asyncio.run(run_test())


def test_async_get_user_activity_counts_requester_and_team_assignments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_test() -> None:
        client = AsyncGlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/",
            client_id="client-id",
            client_secret="client-secret",
        )

        async def fake_search_users(
            rsql_filter="", limit=1, start=0, skip_entity=False
        ):
            return [GlpiUser(user_id="7", name="jdoe")]

        async def fake_search_ticket_records(
            query=None,
            fields=(),
            sort=None,
            batch_size=None,
            include_deleted_ticket=False,
        ):
            return [
                GlpiTicket(id="100", user_recipient=GlpiUser(user_id="7")),
                GlpiTicket(id="101", user_recipient=GlpiUser(user_id="9")),
            ]

        async def fake_get_team_member_records(ticket_id):
            if str(ticket_id) == "101":
                return [GlpiTeamMember(member_type="User", member_id=7, role="1")]
            return []

        async def fake_get_task_durations(**kwargs):
            return {
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "total_duration": 3600,
                "task_count": 1,
                "duration_by_user": {"jdoe": 3600},
                "duration_by_entity": {"Novahe": 3600},
            }

        monkeypatch.setattr(client, "search_users", fake_search_users)
        monkeypatch.setattr(client, "search_ticket_records", fake_search_ticket_records)
        monkeypatch.setattr(
            client, "get_team_member_records", fake_get_team_member_records
        )
        monkeypatch.setattr(client, "get_task_durations", fake_get_task_durations)
        try:
            result = await client.get_user_activity(
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
            await client.close()

    asyncio.run(run_test())


def test_async_get_ticket_context_groups_existing_public_record_helpers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_test() -> None:
        client = AsyncGlpiClient(
            glpi_api_url="https://glpi.example.test/api.php/",
            client_id="client-id",
            client_secret="client-secret",
        )

        async def fake_get_ticket_record(ticket_id):
            return GlpiTicket(id="321")

        async def fake_get_task_records(ticket_id):
            return [GlpiTask(task_id="1")]

        async def fake_get_followup_records(ticket_id):
            return [GlpiFollowup(followup_id="2")]

        async def fake_get_solution_records(ticket_id):
            return [GlpiSolution(solution_id="3")]

        async def fake_get_document_records(ticket_id):
            return [GlpiDocument(document_id="4")]

        monkeypatch.setattr(client, "get_ticket_record", fake_get_ticket_record)
        monkeypatch.setattr(client, "get_task_records", fake_get_task_records)
        monkeypatch.setattr(client, "get_followup_records", fake_get_followup_records)
        monkeypatch.setattr(client, "get_solution_records", fake_get_solution_records)
        monkeypatch.setattr(client, "get_document_records", fake_get_document_records)
        try:
            context = await client.get_ticket_context("321")

            assert context.ticket.id == "321"
            assert [task.task_id for task in context.tasks] == ["1"]
            assert [followup.followup_id for followup in context.followups] == ["2"]
            assert [solution.solution_id for solution in context.solutions] == ["3"]
            assert [document.document_id for document in context.documents] == ["4"]
        finally:
            await client.close()

    asyncio.run(run_test())
