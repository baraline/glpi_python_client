---
name: glpi-reporting-and-context
description: "Aggregate GLPI ticket and task statistics and load grouped ticket contexts with the asynchronous glpi_python_client.GlpiClient. Use for operational reporting, ticket counts grouped by entity/status/priority/type, task duration totals grouped by user and ticket, or one-call ticket context retrieval bundling tickets with timeline records."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to the GLPI v2 API, and credentials allowed to read tickets, tasks, users, entities, and timeline records."
metadata:
  package: glpi-python-client
  version: "0.3.0"
---

# GLPI Reporting And Context

Three custom helpers on `GlpiClient` build on top of the contract-aligned API mixins:

- `get_ticket_context(ticket_id)` returns one `GlpiTicketContext` bundling the primary ticket together with its tasks, followups, solutions, and timeline document links. The five underlying calls run concurrently via `asyncio.gather`.
- `get_ticket_statistics(...)` returns ticket counts grouped by entity, status, priority, and type over an ISO date window applied to GLPI `date_creation`.
- `get_task_statistics(ticket_ids)` returns task duration totals grouped by user and ticket for a caller-supplied list of ticket IDs.

Returned identifiers are raw GLPI numeric values; resolve them with the appropriate `search_*` helpers when human-readable labels are needed.

## Procedure

1. Create a `GlpiClient` with the correct entity/profile scope.
2. For one ticket, call `await client.get_ticket_context(ticket_id)` and read `bundle.ticket`, `bundle.tasks`, `bundle.followups`, `bundle.solutions`, and `bundle.documents`.
3. For ticket counts, call `await client.get_ticket_statistics(start_date=..., end_date=..., default_days=..., extra_filter=...)`. All keyword arguments are optional; the default window is the last 30 days ending today.
4. For task duration totals, first gather the relevant ticket identifiers (typically via `search_tickets`), then call `await client.get_task_statistics(ticket_ids)`.
5. Use the public enums (`GlpiTicketStatus`, `GlpiTicketType`, `GlpiPriority`, ...) when composing additional RSQL filters.

## Examples

Build one ticket context bundle:

```python
context = await client.get_ticket_context(321)
print(context.ticket.id, context.ticket.name)
print(len(context.followups), len(context.tasks))
print(len(context.solutions), len(context.documents))
```

Aggregate ticket statistics for one month, narrowed by status:

```python
from glpi_python_client import GlpiTicketStatus

stats = await client.get_ticket_statistics(
    start_date="2026-01-01",
    end_date="2026-01-31",
    extra_filter=f"status=={int(GlpiTicketStatus.NEW)}",
)
print(stats["entities"])
```

Aggregate task durations across the open tickets of an entity:

```python
open_tickets = await client.search_tickets("status==1", limit=200)
ticket_ids = [t.id for t in open_tickets]

task_stats = await client.get_task_statistics(ticket_ids)
print(task_stats["task_count"], task_stats["total_duration"])
print(task_stats["duration_by_user"])
print(task_stats["duration_by_ticket"])
```

## Gotchas

- All three helpers are async; always `await` them.
- `get_ticket_statistics` validates its date window locally and raises `ValueError` when `default_days < 1` or `start_date > end_date`. The window is applied to `date_creation` server-side.
- `get_task_statistics(ticket_ids=[])` returns zeroed totals without any HTTP call.
- Returned counter keys are raw GLPI numeric identifiers (entity IDs, status numbers, ...) for stable behaviour. Resolve to labels with `search_entities` or the appropriate enum.
- Extra ticket fields (plugin keys, custom dropdowns) flow through `ticket.extra_payload` and are visible on `context.ticket` as well.
