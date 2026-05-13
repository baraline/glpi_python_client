---
name: glpi-document-workflow
description: "Upload, fetch, inspect, link, and download GLPI documents with glpi_python_client GlpiDocument, GlpiClient, AsyncGlpiClient, and GLPIV1Session. Use for ticket attachments, document binary content, document metadata, legacy v1 uploads, or saving downloaded files."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to GLPI, and legacy v1 credentials for upload or direct document linking."
metadata:
  package: glpi-python-client
  version: "0.1.0"
---

# GLPI Document Workflow

After the document refactor, keep high-level imports on the package root. The implementation now lives in `glpi_python_client.clients.v2.sync.documents`, `glpi_python_client.clients.v2.async_.documents`, `glpi_python_client.content.records.parsers.documents`, and `glpi_python_client.clients.api_v1_session` for the legacy gateway.

Use this skill for document metadata, downloads, ticket uploads, and legacy v1 document operations. In async code, use the same public method names on `AsyncGlpiClient` with `await`.

## Procedure

1. Create `GlpiClient` or `AsyncGlpiClient`. Add v1 credentials only for upload or direct legacy-link tasks.
2. For document metadata on a ticket, call `get_document_records(ticket_id)`. Pass `enrich_metadata=False` only when the task prefers raw relation records over per-document metadata lookups.
3. For one document, call `get_document_record(document_id)`.
4. For binary content, call `download_document_content(document_id)` and handle the returned `bytes` according to the user's request.
5. For uploading a new ticket attachment, create `GlpiDocument(ticket_id=..., filename=..., content=..., mime_type=...)` and call `upload_document_to_ticket(document)` on a client configured with v1 credentials.
6. For low-level legacy operations, use `GLPIV1Session.upload_document()` or `GLPIV1Session.link_document_to_ticket()` directly only when the high-level client method does not match the task.

## Examples

Upload bytes to a ticket:

```python
from pathlib import Path

from glpi_python_client import GlpiClient, GlpiDocument

path = Path("diagnostic.txt")

with GlpiClient.from_env(
    v1_base_url="https://glpi.example.com/apirest.php",
    v1_user_token="legacy-user-token",
) as glpi:
    uploaded = glpi.upload_document_to_ticket(
        GlpiDocument(
            ticket_id=321,
            filename=path.name,
            content=path.read_bytes(),
            mime_type="text/plain",
        )
    )
    print(uploaded.document_id)
```

Download content:

```python
from pathlib import Path

from glpi_python_client import GlpiClient

with GlpiClient.from_env() as glpi:
    document = glpi.get_document_record("654")
    content = glpi.download_document_content("654")

Path(document.filename or "glpi-document.bin").write_bytes(content)
```

Link an existing document through the public legacy session API:

```python
from glpi_python_client import GLPIV1Session

v1 = GLPIV1Session(
    base_url="https://glpi.example.com/apirest.php",
    user_token="legacy-user-token",
    app_token="legacy-app-token",
)
try:
    result = v1.link_document_to_ticket(document_id=654, ticket_id=321)
finally:
    v1.close()
```

## Gotchas

- `GlpiDocument.content` is `bytes`. Do not pass text strings as upload content.
- `mime_type` defaults to `application/octet-stream` when omitted.
- `upload_document_to_ticket()` requires `ticket_id`, `filename`, `content`, and a client initialized with `v1_base_url` and `v1_user_token`.
- `upload_document_to_ticket()` returns a copied `GlpiDocument` with normalized ticket/document identifiers; refetch with `get_document_record()` only when the task needs fresh server metadata.
- `download_document_content()` returns bytes and raises `ValueError` on non-200 responses.
- `get_document_records(ticket_id, enrich_metadata=True)` may call `get_document_record()` for metadata enrichment and can tolerate individual metadata failures.
- `AsyncGlpiClient` exposes the same document methods with `await`.
