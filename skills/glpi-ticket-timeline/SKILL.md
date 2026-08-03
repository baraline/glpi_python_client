---
name: glpi-ticket-timeline
description: "Read GLPI ticket timeline records and create or update followups, tasks, solutions, and timeline document links with the synchronous glpi_python_client.GlpiClient or the asynchronous AsyncGlpiClient. Use when handling ticket notes, followups, tasks, solutions, or attached documents on a GLPI ticket timeline."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, and network access to the GLPI v2 API."
metadata:
  package: glpi-python-client
  version: "0.4.1"
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

Attach a document to the ticket timeline. Note `PostTimelineDocument` exposes only one typed field, `timeline_position` (every other `Document_Item` field is read-only on the contract), and the POST URL carries only the ticket id -- so there is no *typed* slot naming which existing document to link. `extra_payload` is merged into the request body verbatim, so `PostTimelineDocument(extra_payload={"documents_id": 654})` does put a document id on the wire; whether the server honours it is untested here. The supported way to put a file on a ticket is `upload_document(..., ticket_id=...)`, which creates the document and the ticket link in one call and requires `v1_base_url` + `v1_user_token` on the client (it raises `RuntimeError` otherwise):

```python
from pathlib import Path

from glpi_python_client import GlpiTimelinePosition, PatchTimelineDocument

path = Path("diagnostic.png")
await client.upload_document(
    filename=path.name,
    content=path.read_bytes(),
    mime_type="image/png",
    ticket_id=321,
)

# Reposition an existing timeline link (document_link_id comes from
# list_ticket_timeline_documents, whose entries are GetDocument records):
await client.update_ticket_timeline_document(
    321,
    654,
    PatchTimelineDocument(timeline_position=GlpiTimelinePosition.LEFT),
)
```

## Gotchas

- The live GLPI v2 server returns each timeline list entry wrapped in `{"type": ..., "item": {...}}` even though the OpenAPI contract documents a flat array. The client unwraps that envelope transparently for the four `list_*` helpers; you receive plain `Get<Entity>` instances. For the document family that entity is `GetDocument` -- the full `/Management/Document` record with `filename`, `mime`, `filepath`, `sha1sum` -- and not `GetTimelineDocument`, which is exported from the package root but is never returned by any client method. `get_ticket_timeline_document` returns `GetDocument` for the same reason. The other three are `list_ticket_followups` -> `GetFollowup`, `list_ticket_tasks` -> `GetTicketTask`, `list_ticket_solutions` -> `GetSolution`.
- `create_*` methods return new identifiers as plain `int`. `update_*` and `delete_*`/`unlink_*` return `None`.
- Timeline `content` fields are Markdown on the Python side, not HTML. `PostFollowup`/`PostTicketTask`/`PostSolution` render Markdown to GLPI's HTML on serialisation, and `GetFollowup`/`GetTicketTask`/`GetSolution` convert the server's HTML back to Markdown on validation -- so `record.content` is always Markdown (`GetFollowup(content="<p>Hello <strong>world</strong></p>").content == "Hello **world**"`). Authoring raw HTML is not an error but is round-tripped through the Markdown converter and can be reshaped; write Markdown.
- Extra server fields (e.g. plugin keys) flow into `record.extra_payload` rather than raising.
- `delete_ticket_*` and `unlink_ticket_timeline_document` accept a keyword-only `force` parameter; pass `force=True` to permanently delete.