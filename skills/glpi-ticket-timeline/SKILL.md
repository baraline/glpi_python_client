---
name: glpi-ticket-timeline
description: "Read GLPI ticket timeline records and create or update followups, tasks, solutions, and timeline document links with the synchronous glpi_python_client.GlpiClient or the asynchronous AsyncGlpiClient. Use when handling ticket notes, followups, tasks, solutions, or attached documents on a GLPI ticket timeline."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, and network access to the GLPI v2 API."
metadata:
  package: glpi-python-client
  version: "0.4.0"
---

# GLPI Ticket Timeline
> The snippets below use `AsyncGlpiClient` (`async with` + `await`). Every method shown also exists on the synchronous `GlpiClient` with the same signature -- replace `async with` with `with`, drop the `await` keyword, and skip the surrounding `async def`/`asyncio.run` scaffolding.

The ticket timeline is exposed by four resource families under `/Assistance/Ticket/{id}/Timeline/{Followup|Task|Solution|Document}`. Each family has matching `Get`/`Post`/`Patch`/`Delete` Pydantic models and the same `list_/get_/create_/update_/delete_` (or `link_`/`unlink_` for documents) shape on `GlpiClient`.

## Procedure

1. Create a `GlpiClient` from the `glpi-client-setup` skill.
2. Read collections with `list_ticket_followups`, `list_ticket_tasks`, `list_ticket_solutions`, and `list_ticket_timeline_documents`.
3. Read individual records with `get_ticket_followup`, `get_ticket_task`, `get_ticket_solution`, `get_ticket_timeline_document`.
4. Create entries with `create_ticket_followup`, `create_ticket_task`, `create_ticket_solution` or `link_ticket_timeline_document`. Each returns the new identifier as `int`.
5. Update entries with `update_ticket_followup`, `update_ticket_task`, `update_ticket_solution`, `update_ticket_timeline_document`.
6. Delete with `delete_ticket_followup`, `delete_ticket_task`, `delete_ticket_solution`, or `unlink_ticket_timeline_document`. Pass `force=True` to permanently delete instead of moving to the trash.

## Examples

Read every timeline list for one ticket:

```python
followups = await client.list_ticket_followups(321)
tasks = await client.list_ticket_tasks(321)
solutions = await client.list_ticket_solutions(321)
documents = await client.list_ticket_timeline_documents(321)
```

Add a followup, a task, and a solution:

```python
from glpi_python_client import PostFollowup, PostSolution, PostTicketTask

followup_id = await client.create_ticket_followup(
    321,
    PostFollowup(content="Triaged: investigation in progress."),
)
task_id = await client.create_ticket_task(
    321,
    PostTicketTask(content="On-site visit", duration=900),
)
solution_id = await client.create_ticket_solution(
    321,
    PostSolution(content="Replaced the access point."),
)
```

Link an existing GLPI document to the ticket timeline:

```python
from glpi_python_client import PostTimelineDocument

link_id = await client.link_ticket_timeline_document(
    321,
    PostTimelineDocument(),
)
```

## Gotchas

- The live GLPI v2 server returns each timeline list entry wrapped in `{"type": ..., "item": {...}}` even though the OpenAPI contract documents a flat array. The client unwraps that envelope transparently for the four `list_*` helpers; you receive plain `Get<Entity>` instances.
- `create_*` methods return new identifiers as plain `int`. `update_*` and `delete_*`/`unlink_*` return `None`.
- Timeline content fields accept GLPI HTML directly.
- Extra server fields (e.g. plugin keys) flow into `record.extra_payload` rather than raising.
- `delete_ticket_*` and `unlink_ticket_timeline_document` accept a keyword-only `force` parameter; pass `force=True` to permanently delete.