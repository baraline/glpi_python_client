---
name: glpi-ticket-workflow
description: "Search, fetch, create, and update GLPI tickets with glpi_python_client GlpiClient, AsyncGlpiClient, and GlpiTicket. Use for GLPI ticket records, ticket filters, fields, pagination, Markdown content, status, priority, category, location, or instance-specific extra_payload values."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to the GLPI high-level API, and credentials accepted by GlpiClient."
metadata:
  package: glpi-python-client
  version: "0.1.0"
---

# GLPI Ticket Workflow

After the ticket refactor, keep imports on the public package root. Ticket behavior now lives in `glpi_python_client.clients.v2.sync.tickets`, `glpi_python_client.clients.v2.async_.tickets`, and `glpi_python_client.content.records.parsers.tickets`, but callers should keep using `GlpiClient`, `AsyncGlpiClient`, and `GlpiTicket`.

Use this skill for ticket reads and writes through the public client and model APIs. In async code, use the same method names on `AsyncGlpiClient` with `await`.

## Procedure

1. Create a `GlpiClient` or `AsyncGlpiClient` with `from_env()` or the explicit setup from the `glpi-client-setup` skill.
2. For reads, call `search_ticket_records()` for lists and `get_ticket_record(ticket_id)` for one ticket.
3. For creates, build a `GlpiTicket` with model field names such as `status`, `category`, and `location`, then call `create_ticket(ticket)`.
4. For updates, build a `GlpiTicket` containing only desired values when possible, then call `update_ticket(ticket_id, ticket, field_mask=(...))` when the update must be constrained.
5. `create_ticket()` returns the new GLPI `ticket_id`. `update_ticket()` returns `None`; refetch with `get_ticket_record()` when the task needs a populated model after a write.

## Examples

Search open tickets and request an additional field:

```python
from glpi_python_client import GlpiClient

with GlpiClient.from_env() as glpi:
    tickets = glpi.search_ticket_records(
        query='status.id=in=(1,2)',
        fields=("request_type",),
        sort="-date_mod",
    )
```

Create a ticket. Markdown content is rendered to GLPI HTML by `to_api_payload()` inside the client:

```python
from glpi_python_client import GlpiClient, GlpiTicket

with GlpiClient.from_env() as glpi:
    ticket_id = glpi.create_ticket(
        GlpiTicket(
            name="Printer issue",
            content="Printer is unreachable from **accounting**.",
            urgency=3,
            impact=3,
            category=10,
            location="12",
        )
    )
    created = glpi.get_ticket_record(ticket_id)
    print(created.id)
```

Update only specific fields:

```python
from glpi_python_client import GlpiClient, GlpiTicket

with GlpiClient.from_env() as glpi:
    glpi.update_ticket(
        "321",
        GlpiTicket(status=3, priority=4),
        field_mask=("status", "priority"),
    )
```

Send site-specific GLPI fields through the public `extra_payload` field:

```python
from glpi_python_client import GlpiTicket

ticket = GlpiTicket(
    name="Badge reader offline",
    extra_payload={"_room_code": "PAR-3F-12", "_asset_tag": "BADGE-044"},
)
```

## Gotchas

- `search_ticket_records()` paginates internally and filters deleted tickets out of results unless `include_deleted_ticket=True` is passed. When `batch_size` is set, it returns an iterator of batches instead of one materialized list.
- `get_ticket_record()` raises `ValueError` when the ticket is deleted unless `include_deleted_ticket=True` is passed, or when it is missing or returned in an unexpected shape.
- `create_ticket()` returns the created ticket ID. `update_ticket()` returns `None`.
- `field_mask` accepts model field names such as `status` and `priority`; the package maps them to the outgoing GLPI payload keys.
- Model content fields use Markdown in Python. Do not pre-render HTML unless the user explicitly needs raw GLPI HTML.
- Put instance-specific payload keys in `extra_payload`; do not reach into protected payload builders.
- `AsyncGlpiClient` exposes the same ticket methods with `await`.
