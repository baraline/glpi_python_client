---
name: glpi-ticket-workflow
description: "Search, fetch, create, update, and delete GLPI tickets with the synchronous glpi_python_client.GlpiClient or the asynchronous AsyncGlpiClient, and the GetTicket/PostTicket/PatchTicket/DeleteTicket models. Use for GLPI ticket records, ticket filters, fields, pagination, status, priority, category, location, or instance-specific extra_payload values."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to the GLPI v2 API, and credentials accepted by GlpiClient."
metadata:
  package: glpi-python-client
  version: "0.4.3"
---

# GLPI Ticket Workflow
> The snippets below use `AsyncGlpiClient` (`async with` + `await`). Every method shown also exists on the synchronous `GlpiClient` with the same signature -- replace `async with` with `with`, drop the `await` keyword, and skip the surrounding `async def`/`asyncio.run` scaffolding.

Use this skill for ticket reads and writes through the public client. Tickets live under `/Assistance/Ticket` on the GLPI v2 API and are exposed by six methods, present on both `GlpiClient` and `AsyncGlpiClient` with identical signatures: `search_tickets`, `iter_search_tickets`, `get_ticket`, `create_ticket`, `update_ticket`, and `delete_ticket`.

## Procedure

1. Create a `GlpiClient` from the `glpi-client-setup` skill.
2. For reads, call `await client.search_tickets(rsql_filter, limit=..., start=...)` for lists and `await client.get_ticket(ticket_id)` for one ticket.
3. For creates, build a `PostTicket(name=..., content=...)` and call `await client.create_ticket(ticket)`. The method returns the new GLPI ticket ID.
4. For updates, build a `PatchTicket` containing only the fields you intend to change and call `await client.update_ticket(ticket_id, ticket)`. The method returns `None`.
5. For deletes, call `await client.delete_ticket(ticket_id, force=True|False|None)`. `force=True` permanently deletes; `False`/`None` move the record to the trash.
6. Refetch with `get_ticket()` when the task needs a populated model after a write.

## Examples

Search open tickets:

```python
tickets = await client.search_tickets("is_deleted==false;status==1", limit=20)  # v2 search returns trashed tickets unless `is_deleted` is pinned
```

Create a ticket. Content fields accept Markdown and are converted to GLPI's HTML transport format transparently:

```python
from glpi_python_client import PostTicket

ticket_id = await client.create_ticket(
    PostTicket(
        name="Printer issue",
        content="Printer is unreachable from **accounting**.",
    )
)
created = await client.get_ticket(ticket_id)
```

Patch only specific fields:

```python
from glpi_python_client import PatchTicket

await client.update_ticket(
    321,
    PatchTicket(content="Updated diagnosis"),
)
```

Send instance-specific GLPI fields through the public `extra_payload`:

```python
from glpi_python_client import PostTicket

ticket = PostTicket(
    name="Badge reader offline",
    content="Badge reader is offline.",
    extra_payload={"_room_code": "PAR-3F-12", "_asset_tag": "BADGE-044"},
)
```

## Gotchas

- On `AsyncGlpiClient` every ticket method is a coroutine and must be awaited; on `GlpiClient` the same methods are ordinary blocking calls and must not be awaited. `iter_search_tickets` is the exception to the shape: it is an async generator on `AsyncGlpiClient` (`async for`) and a plain generator on `GlpiClient` (`for`), so it is iterated, not awaited, on either surface.
- `search_tickets` accepts a raw RSQL filter string; pagination is via the keyword-only `limit` and `start` (it also takes `sort` and `fields`). To walk a whole result set use the batch iterator `iter_search_tickets(rsql_filter, batch_size=50, sort=..., fields=...)`, which advances `start` itself and yields one `list[GetTicket]` page per step, stopping when a page comes back shorter than `batch_size` — `async for batch in client.iter_search_tickets(...)` on `AsyncGlpiClient`, `for batch in client.iter_search_tickets(...)` on `GlpiClient`.
- **`search_tickets` and every other `search_*` raise `GlpiStatusError` on a 4xx.** This changed: they used to check the response status only when the caller passed a `failure_message`, which none of the seven `search_*` helpers does, so a GLPI error body was coerced to `[]` and a malformed RSQL filter, a 403, a missing route and a genuinely empty result set were indistinguishable. `_resource_list` now checks the status on every call, so **an empty list means the server said the result set is empty**. The iterators inherit that: a 4xx raises instead of making the first page short and ending the walk silently. Note the *other* fail-open path is unchanged and still bites -- GLPI v2 ignores a filter field it does not recognise and answers 200 with the whole unfiltered table, so a filter that returns rows is still not proof it was applied.
- `create_ticket` returns the new ticket ID. `update_ticket` and `delete_ticket` return `None`.
- The GLPI server is the authoritative validator. Extra keys returned by the server flow into `ticket.extra_payload` rather than raising. Caller-provided `extra_payload` keys win on conflicts.
- Read-only fields such as `status` are intentionally absent from `PostTicket`/`PatchTicket`; the server controls those transitions. `global_validation` is the exception -- it *is* declared on both write models, typed `GlpiGlobalValidation | None`, whose members are `NONE = 1`, `WAITING = 2`, `ACCEPTED = 3`, `REFUSED = 4`. `GlpiGlobalValidation` is exported from the package root alongside `GlpiTicketStatus` (`NEW = 1`, `ASSIGNED = 2`, `PLANNED = 3`, `PENDING = 4`, `SOLVED = 5`, `CLOSED = 6`, `VALIDATION = 10`), `GlpiTicketType` (`INCIDENT = 1`, `REQUEST = 2`) and `GlpiPriority`; `status` and the rest stay readable on `GetTicket`.