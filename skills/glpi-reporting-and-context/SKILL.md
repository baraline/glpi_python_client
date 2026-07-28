---
name: glpi-reporting-and-context
description: "Aggregate GLPI ticket and task statistics and load grouped ticket contexts with the synchronous glpi_python_client.GlpiClient or the asynchronous AsyncGlpiClient. Use for operational reporting, ticket counts grouped by entity/status/priority/type, task duration totals grouped by user/entity/ticket, per-user activity reports, batch-streamed pagination of search results, or one-call ticket context retrieval bundling tickets with timeline records."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to the GLPI v2 API, and credentials allowed to read tickets, tasks, users, entities, and timeline records."
metadata:
  package: glpi-python-client
  version: "0.4.0"
---

# GLPI Reporting And Context
> The snippets below use `AsyncGlpiClient` (`async with` + `await`). Every method shown also exists on the synchronous `GlpiClient` with the same signature -- replace `async with` with `with`, drop the `await` keyword, and skip the surrounding `async def`/`asyncio.run` scaffolding. The `iter_search_*` helpers are async **generators** on the async client: iterate them with `async for` instead of `await`.

Custom helpers on `GlpiClient` build on top of the contract-aligned API mixins:

- `get_ticket_context(ticket_id)` returns one `GlpiTicketContext` bundling the primary ticket together with its tasks, followups, solutions, and timeline document links. The five underlying calls are independent and are issued through the library's internal `gather` helper, so they fan out concurrently on `AsyncGlpiClient` and run one after another on `GlpiClient`. Expect the synchronous call to take roughly five round trips.
- `get_ticket_statistics(...)` returns ticket counts grouped by entity, status, priority, and type over an ISO date window applied to GLPI `date_creation`. Accepts `entity_id`, `entity_name` (substring match resolved via `search_entities`), and `extra_filter` (raw RSQL AND-joined with the window).
- `get_task_statistics(ticket_ids)` returns task duration totals grouped by user and ticket for a caller-supplied list of ticket IDs.
- `get_task_durations(...)` is a higher-level helper that internally iterates `iter_search_tickets` with a date/entity/user filter, computes per-user and per-entity duration totals, and optionally returns a flat per-task list when `return_task_details=True`.
- `get_user_activity(...)` aggregates per-user activity (tickets as technician, tickets as recipient, task durations) over a date window; resolves users by `user_id`, `username`, `realname`, or `firstname` and merges users that share the same display key.
- `iter_search_tickets`, `iter_search_users`, `iter_search_entities` yield successive `list[...]` batches of contract models and stop on the first short batch. They handle pagination so callers do not manage `start` cursors manually.

Returned identifiers are raw GLPI numeric values; resolve them with the appropriate `search_*` helpers when human-readable labels are needed.

## Procedure

1. Create a client (`GlpiClient` or `AsyncGlpiClient`) with the correct entity/profile scope.
2. For one ticket, call `await client.get_ticket_context(ticket_id)` and read `bundle.ticket`, `bundle.tasks`, `bundle.followups`, `bundle.solutions`, and `bundle.documents`.
3. For ticket counts, call `await client.get_ticket_statistics(start_date=..., end_date=..., default_days=..., entity_id=..., entity_name=..., extra_filter=...)`. All keyword arguments are optional; the default window is the last 30 days ending today.
4. For task duration totals on a known ticket list, call `await client.get_task_statistics(ticket_ids)`. For an end-to-end "duration over a window with filters" report, call `await client.get_task_durations(...)` instead; it gathers the ticket IDs internally.
5. For a per-user activity report, call `await client.get_user_activity(username=..., start_date=..., end_date=...)`. Supply at least one of `user_id`, `username`, `realname`, `firstname`.
6. For memory-bounded pagination over large result sets, iterate `iter_search_tickets` / `iter_search_users` / `iter_search_entities` with `async for batch in client.iter_search_*(...): ...`.
7. Use the public enums (`GlpiTicketStatus`, `GlpiTicketType`, `GlpiPriority`, ...) when composing additional RSQL filters.

## Examples

Build one ticket context bundle:

```python
context = await client.get_ticket_context(321)
print(context.ticket.id, context.ticket.name)
print(len(context.followups), len(context.tasks))
print(len(context.solutions), len(context.documents))
```

Aggregate ticket statistics for one month, narrowed by status and entity:

```python
from glpi_python_client import GlpiTicketStatus

stats = await client.get_ticket_statistics(
    start_date="2026-01-01",
    end_date="2026-01-31",
    entity_id=3,
    extra_filter=f"status=={int(GlpiTicketStatus.NEW)}",
)
print(stats["entities"])
```

Aggregate task durations across the open tickets of an entity using
`get_task_durations` (no manual ticket-list gathering):

```python
durations = await client.get_task_durations(
    entity_id=3,
    user_id=42,
    return_task_details=True,
)
print(durations["total_duration"], durations["task_count"])
print(durations["duration_by_entity"])
for task in durations["tasks"] or []:
    print(task["task_id"], task["ticket_id"], task["duration"])
```

Build a per-user activity report:

```python
report = await client.get_user_activity(
    username="alice",
    start_date="2026-01-01",
    end_date="2026-01-31",
)
for display_name, data in report["users"].items():
    print(
        display_name,
        data["tickets_as_technician"],
        data["tickets_as_recipient"],
        data["task_durations"]["total_duration"],
    )
```

Stream all open tickets without loading the full result set in memory:

```python
total = 0
async for batch in client.iter_search_tickets("status==1", batch_size=200):
    total += len(batch)
    for ticket in batch:
        ...  # process each ticket
print(f"processed {total} tickets")
```

## Gotchas

- All helpers shown above are async on `AsyncGlpiClient`; always `await` them. The `iter_search_*` helpers are async **generators** -- use `async for`, not `await`.
- **Bound any fan-out you build on top of these helpers.** Calling `get_ticket_context` for every ticket in a batch with a bare `asyncio.gather` gets *slower* as the batch grows: the underlying HTTP pool rescans itself on every request assignment, so a wide fan-out saturates the event loop and the observed concurrency falls. Cap it instead:

  ```python
  gate = asyncio.Semaphore(16)

  async def one(ticket_id):
      async with gate:
          return await client.get_ticket_context(ticket_id)

  contexts = await asyncio.gather(*(one(t.id) for t in batch))
  ```

  Measured against a 50 ms server, a fan-out of 16 took 350 ms unbounded and 108 ms capped at 16. This is a property of the HTTP layer, not of this library, and there is no version to upgrade to.
- `get_ticket_statistics`, `get_task_durations`, and `get_user_activity` validate their date window locally and raise `ValueError` when `default_days < 1` or `start_date > end_date`. The window is applied to `date_creation` server-side.
- `get_task_statistics(ticket_ids=[])` returns zeroed totals without any HTTP call. `get_task_durations` likewise returns zeroed totals when no tickets match the filter, and short-circuits with zeros when `entity_name` resolves to no entities.
- `get_user_activity` raises `ValueError` when no identifier is supplied and when the criteria match no users. Multiple users with the same `f"{firstname} {realname}"` display key are merged into one bucket.
- Returned counter keys are raw GLPI numeric identifiers (entity IDs, status numbers, user IDs as strings) for stable behaviour. Resolve to labels with `search_entities` / `get_user` or the appropriate enum.
- Extra ticket fields (plugin keys, custom dropdowns) flow through `ticket.extra_payload` and are visible on `context.ticket` as well.