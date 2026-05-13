---
name: glpi-ticket-timeline
description: "Read GLPI ticket timelines and create or update public/private followups plus create solutions with glpi_python_client. Use when handling ticket notes, followups, tasks, solutions, timeline documents, attachment document IDs, or Markdown support responses."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to the GLPI high-level API, and optional legacy v1 credentials for attachment ID lookup."
metadata:
  package: glpi-python-client
  version: "0.1.0"
---

# GLPI Ticket Timeline

After the timeline refactor, keep imports on the public package root. Timeline behavior now lives in `glpi_python_client.clients.v2.sync.timeline`, `glpi_python_client.clients.v2.async_.timeline`, and `glpi_python_client.content.records.parsers.timeline`.

Use this skill for ticket timeline records: followups, tasks, solutions, linked documents, and attachment IDs. In async code, use the same method names on `AsyncGlpiClient` with `await`.

## Procedure

1. Create a `GlpiClient` or `AsyncGlpiClient`.
2. Fetch timeline data with the method matching the record type: `get_followup_records()`, `get_task_records()`, `get_solution_records()`, or `get_document_records()`.
3. To add a note, create `GlpiFollowup(content=..., is_private=...)` and call `create_followup(ticket_id, followup)`. The method returns the created `followup_id`.
4. To update a note, call `update_followup(ticket_id, followup_id, followup)`. The method returns `None` on success.
5. To add a resolution, create `GlpiSolution(content=...)` and call `create_solution(ticket_id, solution)`. The method returns the created `solution_id`.
6. Use `get_followup_attachment_document_ids()` or `get_solution_attachment_document_ids()` only when legacy v1 credentials are configured.
7. Refetch followups or solutions after writes when the task needs hydrated records instead of the created IDs.

## Examples

Read timeline records:

```python
from glpi_python_client import GlpiClient

with GlpiClient.from_env() as glpi:
    ticket_id = "321"
    followups = glpi.get_followup_records(ticket_id)
    tasks = glpi.get_task_records(ticket_id)
    solutions = glpi.get_solution_records(ticket_id)
    documents = glpi.get_document_records(ticket_id)
```

Post a private followup:

```python
from glpi_python_client import GlpiClient, GlpiFollowup

with GlpiClient.from_env() as glpi:
    followup_id = glpi.create_followup(
        "321",
        GlpiFollowup(
            content="Internal check: replacement toner is available.",
            is_private=True,
        ),
    )
    print(followup_id)
```

Create a solution:

```python
from glpi_python_client import GlpiClient, GlpiSolution

with GlpiClient.from_env() as glpi:
    solution_id = glpi.create_solution(
        "321",
        GlpiSolution(content="Reconnected the printer and validated a test page."),
    )
    print(solution_id)
```

Read document IDs attached directly to a followup:

```python
from glpi_python_client import GlpiClient

with GlpiClient.from_env() as glpi:
    document_ids = glpi.get_followup_attachment_document_ids("987")
```

## Gotchas

- `GlpiTask` is read-only through the high-level client today; there is no public `create_task()` method.
- `create_followup()` and `create_solution()` return created IDs. `update_followup()` returns `None`.
- `GlpiSolution` is writable for create/delete workflows, but there is no public `update_solution()` helper today.
- Followup and solution content should be Markdown in Python. The package renders it to GLPI HTML for outgoing payloads.
- Timeline read methods return an empty list on non-success responses instead of raising for most record types.
- Attachment ID lookup uses the configured legacy v1 session and returns an empty tuple when v1 is unavailable or fails.
- `AsyncGlpiClient` exposes the same timeline methods with `await`.
