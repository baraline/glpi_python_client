---
name: glpi-document-workflow
description: "Manage GLPI document metadata, upload binary content via the legacy v1 fallback, download document binaries, and link documents to a ticket timeline with the synchronous glpi_python_client.GlpiClient or the asynchronous AsyncGlpiClient, and the GetDocument/PostDocument/PatchDocument/DeleteDocument models. Use for ticket attachments, document binary content, document metadata, or saving downloaded files."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to the GLPI v2 API, and v1 credentials configured on the client for binary uploads."
metadata:
  package: glpi-python-client
  version: "0.4.1"
---

# GLPI Document Workflow
> The snippets below use `AsyncGlpiClient` (`async with` + `await`). Every method shown also exists on the synchronous `GlpiClient` with the same signature -- replace `async with` with `with`, drop the `await` keyword, and skip the surrounding `async def`/`asyncio.run` scaffolding.

Document metadata uses the standard `Get`/`Post`/`Patch`/`Delete` shape on `/Management/Document`. Binary content uses two dedicated helpers: `download_document_content` for downloads and `upload_document` for uploads through the legacy v1 fallback session (the v2 contract does not advertise a binary upload endpoint).

The `GLPIV1Session` class is no longer part of the public surface; the v1 session is fully internal and is configured by passing `v1_base_url` and `v1_user_token` to `GlpiClient`.

## Procedure

1. Create a `GlpiClient`. For uploads, also pass `v1_base_url` and `v1_user_token` (and optionally `v1_app_token`).
2. Search documents with `await client.search_documents(rsql_filter, limit=..., start=...)`.
3. Fetch one document's metadata with `await client.get_document(document_id)`.
4. Create a metadata-only record with `PostDocument(...)` and `await client.create_document(document)`. The method returns the new ID.
5. Update with `PatchDocument(...)` and `await client.update_document(document_id, document)`.
6. Delete with `await client.delete_document(document_id, force=True|False|None)`.
7. Download bytes with `content = await client.download_document_content(document_id)`.
8. Upload bytes with `await client.upload_document(filename=..., content=..., mime_type=..., ticket_id=..., entity_id=...)`.
9. To attach an existing GLPI document to a ticket timeline, use `link_ticket_timeline_document` from the timeline skill.

## Examples

Download a document:

```python
from pathlib import Path

document = await client.get_document(654)
content = await client.download_document_content(654)
Path(document.filename or "glpi-document.bin").write_bytes(content)
```

Upload a binary attachment to a ticket:

```python
from pathlib import Path

path = Path("diagnostic.png")
result = await client.upload_document(
    filename=path.name,
    content=path.read_bytes(),
    mime_type="image/png",
    ticket_id=321,
)
print(result)  # raw v1 response payload
```

Create metadata only (no binary):

```python
from glpi_python_client import PostDocument

document_id = await client.create_document(PostDocument(name="Diagnostic notes"))
```

## Gotchas

- `upload_document` raises `RuntimeError` when the v1 session is not configured. Pass `v1_base_url` and `v1_user_token` to the client constructor or `from_env`.
- `upload_document` requires a non-empty `filename`. On the async client the multipart POST is awaited like any other call, so the event loop is not blocked.
- `download_document_content` returns `bytes` and raises on non-200 responses.
- `mime_type` defaults to `application/octet-stream` when omitted on `upload_document`.
- The snippets above use `AsyncGlpiClient`, so every call is awaited. The same methods on the synchronous `GlpiClient` are plain blocking calls -- drop the `await`.
- The `delete_document(force=True)` flag permanently deletes; omit (or `False`) to move to the trash.