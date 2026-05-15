---
name: glpi-ticket-workflow
description: "Search, fetch, create, update, and delete GLPI tickets with the asynchronous glpi_python_client.GlpiClient and the GetTicket/PostTicket/PatchTicket/DeleteTicket models. Use for GLPI ticket records, ticket filters, fields, pagination, status, priority, category, location, or instance-specific extra_payload values."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to the GLPI v2 API, and credentials accepted by GlpiClient."
metadata:
  package: glpi-python-client
  version: "0.3.0"
---

# GLPI Ticket Workflow

Use this skill for ticket reads and writes through the public asynchronous client. Tickets live under `/Assistance/Ticket` on the GLPI v2 API and are exposed by five `GlpiClient` methods: `search_tickets`, `get_ticket`, `create_ticket`, `update_ticket`, and `delete_ticket`.

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
tickets = await client.search_tickets("status==1", limit=20)
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

- All ticket methods are async; always `await` them.
- `search_tickets` accepts a raw RSQL filter string; pagination is via `limit` and `start`. There is no batch iterator.
- `create_ticket` returns the new ticket ID. `update_ticket` and `delete_ticket` return `None`.
- The GLPI server is the authoritative validator. Extra keys returned by the server flow into `ticket.extra_payload` rather than raising. Caller-provided `extra_payload` keys win on conflicts.
- Read-only fields such as `status` are intentionally absent from `PostTicket`/`PatchTicket`; the server controls those transitions.
