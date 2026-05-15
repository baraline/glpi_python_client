---
name: glpi-reporting-and-context
description: "Search GLPI entities and tasks, aggregate task durations and ticket statistics, inspect user activity, and load grouped ticket contexts with glpi_python_client public package-root imports. Use for operational reporting, Novahe-style migration work, entity lookup, task-duration reports, ticket counts, requester or technician activity, and one-call ticket context retrieval."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to the GLPI high-level API, and credentials allowed to read tickets, tasks, users, entities, and related timeline records."
metadata:
  package: glpi-python-client
  version: "0.1.0"
---

# GLPI Reporting And Context

Keep imports on the public package root. Reporting and context behavior now
lives behind `GlpiClient`, `AsyncGlpiClient`, `GlpiEntity`, `GlpiTask`,
`GlpiTicketContext`, `GlpiTicketStatus`, `GlpiPriority`, and
`GlpiTicketType`.

Use this skill when the task needs typed entity lookup, global task search,
task duration aggregation, ticket statistics, user activity summaries, or one
grouped ticket context bundle. In async code, use the same method names on
`AsyncGlpiClient` with `await`.

## Procedure

1. Create a `GlpiClient` or `AsyncGlpiClient` with the correct entity and profile scope.
2. Search entities with `search_entities(rsql_filter, limit=..., start=...)` when the workflow needs a typed entity ID or full entity path.
3. Search global tasks with `search_task_records(query=..., fields=..., sort=..., batch_size=...)` when the workflow needs raw task rows before aggregation.
4. Use `get_task_durations()` for duration totals grouped by user and entity.
5. Use `get_ticket_statistics()` for counts grouped by entity, status, priority, and type.
6. Use `get_user_activity()` when the task needs requester counts, technician counts, and nested task-duration summaries for one or more users.
7. Use `get_ticket_context(ticket_id)` when the task needs the primary ticket plus tasks, followups, solutions, and documents in one object.

## Examples

Search entities and tasks:

```python
from glpi_python_client import GlpiClient

with GlpiClient.from_env() as glpi:
    entities = glpi.search_entities(
        rsql_filter='name=like=*novahe*',
        limit=10,
    )
    tasks = glpi.search_task_records(
        query='date=ge=2026-01-01;date=le=2026-01-31',
        fields=("id", "tickets_id", "users_id", "actiontime", "date", "content"),
        sort="date:desc",
    )
```

Aggregate task durations and ticket statistics:

```python
from glpi_python_client import GlpiClient, GlpiTicketStatus

with GlpiClient.from_env() as glpi:
    durations = glpi.get_task_durations(
        start_date="2026-01-01",
        end_date="2026-01-31",
        entity_name="Novahe",
        return_task_details=True,
    )
    stats = glpi.get_ticket_statistics(
        entity_name="Novahe",
        start_date="2026-01-01",
        end_date="2026-01-31",
        extra_filter=GlpiTicketStatus.NEW.rsql_equals("status"),
    )
```

Inspect user activity and one grouped ticket context:

```python
from glpi_python_client import GlpiClient

with GlpiClient.from_env() as glpi:
    activity = glpi.get_user_activity(
        email="jane.doe@example.com",
        start_date="2026-01-01",
        end_date="2026-01-31",
    )
    context = glpi.get_ticket_context("321")
    print(activity["users"])
    print(context.ticket.id, len(context.tasks), len(context.followups))
```

## Gotchas

- `search_task_records()` returns a full list by default and becomes a batch iterator only when `batch_size` is provided.
- `get_task_durations()` validates dates locally and raises `ValueError` when the window is invalid or when conflicting entity filters cannot resolve to the same entity.
- `get_user_activity()` requires at least one user identifier.
- `get_ticket_context()` only composes existing public record methods; it does not bypass the normal ticket, timeline, or document parsing path.
- Requested ticket or task fields that do not map to typed public model attributes remain available through `extra_payload`.
- `AsyncGlpiClient` exposes the same reporting and context methods with `await`.