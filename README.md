# glpi-python-client

`glpi-python-client` is an object oriented & typed Python client to simplify interactions with GLPI ITSM instances for GLPI 11. We convert GLPI HTML content into Markdown and define a set of pydantic objects (Users, Ticket, Followup, Documents, etc.) for easier interactions with other systems. For now, it mostly focus on Ticket-related operations.

This project is currently based on the experience I've had on the field with a few GLPI instances. Notably on the interaction with documents, which is currently a mix of v1 and v2 REST API, as some functionnalities were not working or available yet on v2. For exemple, it uses the legacy v1 document-upload API, as I couldn't make it work on v2.

If you notice incompatibilities with your own instance, open an issue with the detail so I can try to find a more generic way to expose this part of the API.

## Features

- OAuth2 token handling with client credentials, user credentials, or both,
  plus expiry-based and optional interval-based refresh support.
- Synchronous and asynchronous high-level clients with matching API methods.
- Paginated ticket search and ticket detail retrieval.
- Helpers for ticket followups, tasks, solutions, documents, team members,
  users, and locations.
- Public delete helpers for tickets, followups, solutions, documents, users,
  locations, and ticket team members.
- Optional legacy GLPI v1 session support for document upload and document links.
- Field-validated Pydantic models with typed `to_api_payload()` helpers.
- Markdown in Python for ticket, followup, task, and solution content, with
    automatic HTML conversion for GLPI payloads.
- Standard `pyproject.toml` packaging, typed package marker, and colocated pytest tests.

## Installation

```bash
pip install glpi-python-client
```

For local development:

```bash
python -m pip install -e .[dev]
python -m pytest
```

## Quick Start

Create the client with the values your application already owns: the GLPI API
URL and at least one complete auth pair.

Supported auth combinations:

- `client_id` and `client_secret`
- `username` and `password`
- both pairs together

The example below uses both pairs because that is the most explicit setup for a
user-scoped confidential OAuth client.

Optional constructor arguments shown below:

- `glpi_entity`: numeric GLPI entity ID for the `GLPI-Entity` header. Omit it
    when the API user should keep its default entity.
- `glpi_profile`: numeric GLPI profile ID for the `GLPI-Profile` header. Omit
    it when the API user already starts in the correct profile.
- `auth_token_refresh`: optional number of seconds between proactive OAuth token
    refreshes. Omit it or pass `None` to disable interval-based refresh.

Using the client as a context manager clears the cached OAuth tokens and closes
the underlying HTTP sessions automatically when the block exits.

```python
from glpi_python_client import GlpiClient, GlpiTicket

DEFAULT_ENTITY_ID = 1
TECHNICIAN_PROFILE_ID = 4

with GlpiClient(
    glpi_api_url="https://glpi.example.com/api.php",
    client_id="oauth-client-id",
    client_secret="oauth-client-secret",
    username="api-user",
    password="api-password",
    glpi_entity=DEFAULT_ENTITY_ID,
    glpi_profile=TECHNICIAN_PROFILE_ID,
) as glpi:
    tickets = glpi.search_ticket_records(query='status.id=in=(1,2)', fields=("request_type",))
    ticket_id = glpi.create_ticket(
        GlpiTicket(
            name="Printer issue",
            content="The printer is not reachable from the office network.",
            urgency=3,
            impact=3,
        )
    )
    ticket = glpi.get_ticket_record(ticket_id)
```

`search_ticket_records()` returns one fully materialized list by default. Pass
`batch_size` to iterate over batches instead when you need to stream larger
result sets:

Deleted tickets are excluded by default from `search_ticket_records()` and
`get_ticket_record()`. Pass `include_deleted_ticket=True` when you need GLPI
tickets marked as deleted.

```python
for batch in glpi.search_ticket_records(query='status.id=in=(1,2)', batch_size=200):
    for ticket in batch:
        print(ticket.id)
```

Async applications can use `AsyncGlpiClient` with the same constructor options
and await remote operations. The async client currently uses the same
`requests` transport behind an async wrapper, which keeps the public API
awaitable while preserving the shared sync transport behavior:

```python
from glpi_python_client import AsyncGlpiClient, GlpiTicket

async with AsyncGlpiClient(
    glpi_api_url="https://glpi.example.com/api.php",
    client_id="oauth-client-id",
    client_secret="oauth-client-secret",
    username="api-user",
    password="api-password",
    auth_token_refresh=900,
) as glpi:
    tickets = await glpi.search_ticket_records(query='status.id=in=(1,2)')
    ticket_id = await glpi.create_ticket(GlpiTicket(name="Printer issue"))
    ticket = await glpi.get_ticket_record(ticket_id)
```

Create operations return the new GLPI identifier. Update, add, remove, and
delete operations return `None` and raise on error.

Model content fields such as `GlpiTicket.content` and `GlpiFollowup.content` use
Markdown in Python. Fetched GLPI HTML is converted to Markdown, and outgoing
Markdown is rendered to HTML when API payloads are built. `GlpiDocument.content`
remains `bytes` for binary upload and download workflows.

`GlpiTicket` follows GLPI ticket field names directly, including `id`,
`status`, `type`, `category`, `location`, `date_creation`, `date_mod`,
`date_close`, `user_recipient`, `user_editor`, and `team`.

If your application already exposes those same values through environment
variables, `GlpiClient.from_env()` is available as a convenience utility:

```python
from glpi_python_client import GlpiClient

client = GlpiClient.from_env()
```

Set `GLPI_AUTH_TOKEN_REFRESH` to a positive number of seconds to enable
interval-based OAuth token refreshes. `AsyncGlpiClient.from_env()` reads the
same variables and explicit overrides.

By default it reads the `GLPI_`-prefixed values that match the constructor
arguments, including `GLPI_API_URL`. For authentication,
provide at least one complete pair: `GLPI_CLIENT_ID` with
`GLPI_CLIENT_SECRET`, `GLPI_USERNAME` with `GLPI_PASSWORD`, or both.

## Legacy v1 Document Uploads

Some GLPI installations still require the v1 API for document upload and link
operations. Pass the v1 endpoint and tokens when constructing the client:

- `v1_base_url` is optional and only needed when your GLPI instance exposes
    document upload and link operations through a separate v1 endpoint such as
    `/api.php/v1` or `/apirest.php`.
- `v1_user_token` is required when `v1_base_url` is supplied.
- `v1_app_token` is optional when that v1 endpoint does not require an app
    token.

```python
from glpi_python_client import GlpiClient, GlpiDocument

V1_DOCUMENT_BASE_URL = "https://glpi.example.com/api.php/v1"
V1_DOCUMENT_USER_TOKEN = "user-token"
V1_DOCUMENT_APP_TOKEN = "app-token"

with GlpiClient(
    glpi_api_url="https://glpi.example.com/api.php",
    client_id="oauth-client-id",
    client_secret="oauth-client-secret",
    username="api-user",
    password="api-password",
    v1_base_url=V1_DOCUMENT_BASE_URL,
    v1_user_token=V1_DOCUMENT_USER_TOKEN,
    v1_app_token=V1_DOCUMENT_APP_TOKEN,
) as glpi:
    uploaded = glpi.upload_document_to_ticket(
        GlpiDocument(
            ticket_id=123,
            filename="diagnostic.txt",
            content=b"network trace",
            mime_type="text/plain",
        )
    )
```

## Project Status

The package is structured for open-source development and currently focuses on
the endpoints imported from the previous GLPI integration. New endpoint helpers
should be added as typed model methods plus focused transport tests.

## Documentation

- [Usage guide](docs/usage.md)
- [Development guide](docs/development.md)
- [Publishing checklist](docs/publishing.md)

The Read the Docs/Sphinx source lives in [docs](docs). Build it locally with:

```bash
python -m pip install -e .[docs]
python -m sphinx -b html docs docs/_build/html
```
