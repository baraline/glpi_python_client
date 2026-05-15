# Usage Guide

`glpi-python-client` exposes synchronous and asynchronous client objects:
`glpi_python_client.GlpiClient` and `glpi_python_client.AsyncGlpiClient`.

## Create a Client

Create the client with the GLPI API URL and at least one complete authentication
pair that your application already manages:

- `glpi_api_url` is required.
- `client_id` and `client_secret` are a complete OAuth client credential pair.
- `username` and `password` are a complete user credential pair.
- Provide either credential pair, or both pairs together, depending on your GLPI
    instance configuration.
- `glpi_entity` is optional and sends the `GLPI-Entity` header when requests
    must stay in one explicit GLPI entity.
- `glpi_profile` is optional and sends the `GLPI-Profile` header when the API
    user must switch to one explicit profile.
- `auth_token_refresh` is optional and sets the number of seconds between
    proactive OAuth token refreshes. Use `None` to disable interval-based
    refresh.

```python
from glpi_python_client import GlpiClient

client = GlpiClient(
    glpi_api_url="https://glpi.example.com/api.php",
    client_id="oauth-client-id",
    client_secret="oauth-client-secret",
    username="api-user",
    password="api-password",
    glpi_entity=1,
    glpi_profile=4,
)
```

Use the client as a context manager when possible so cached OAuth tokens are
cleared and HTTP sessions are closed automatically:

```python
from glpi_python_client import GlpiClient

with GlpiClient(
    glpi_api_url="https://glpi.example.com/api.php",
    client_id="oauth-client-id",
    client_secret="oauth-client-secret",
    username="api-user",
    password="api-password",
) as glpi:
    tickets = glpi.search_ticket_records()
```

`search_ticket_records()` returns a full `list[GlpiTicket]` by default. When
you pass `batch_size`, it becomes a lazy iterator of ticket batches:

Deleted tickets are excluded by default from `search_ticket_records()` and
`get_ticket_record()`. Pass `include_deleted_ticket=True` when you need GLPI
tickets marked as deleted.

```python
for batch in glpi.search_ticket_records(batch_size=200):
    for ticket in batch:
        print(ticket.id)
```

Async applications can use the matching async client surface. The async client
currently wraps the shared `requests` transport so applications can await client
methods without changing the sync transport behavior:

```python
from glpi_python_client import AsyncGlpiClient

async with AsyncGlpiClient(
    glpi_api_url="https://glpi.example.com/api.php",
    client_id="oauth-client-id",
    client_secret="oauth-client-secret",
    username="api-user",
    password="api-password",
    auth_token_refresh=900,
) as glpi:
    tickets = await glpi.search_ticket_records()
```

## Utility Constructor

When the same values are already exposed as environment variables,
`GlpiClient.from_env()` offers a convenience constructor.

`GlpiClient.from_env()` reads the following variables by default.

Required variables:

- `GLPI_API_URL`: GLPI high-level API URL, usually ending
    in `/api.php`.
- At least one complete auth pair: `GLPI_CLIENT_ID` with
    `GLPI_CLIENT_SECRET`, `GLPI_USERNAME` with `GLPI_PASSWORD`, or both pairs.

Optional variables:

- `GLPI_ENTITY`: entity routing header.
- `GLPI_PROFILE`: profile routing header.
- `GLPI_ENTITY_RECURSIVE`: enables recursive entity scope when truthy.
- `GLPI_LANGUAGE`: Accept-Language header. Defaults to `en_GB`.
- `GLPI_VERIFY_SSL`: set to `false` only for trusted internal test instances.
- `GLPI_AUTH_TOKEN_REFRESH`: seconds between proactive OAuth token refreshes.
- `GLPI_V1_BASE_URL`: explicit v1 document API URL, for example
    `/api.php/v1` or `/apirest.php`.
- `GLPI_V1_USER_TOKEN`: legacy v1 user token.
- `GLPI_V1_APP_TOKEN`: legacy v1 app token.

## Tickets

```python
from glpi_python_client import GlpiTicket

ticket = GlpiTicket(
    name="Printer issue",
    content="The printer is not reachable from the office network.",
    urgency=3,
    impact=3,
)
ticket_id = glpi.create_ticket(ticket)
created = glpi.get_ticket_record(ticket_id)
glpi.delete_ticket(ticket_id)
```

Create operations return the created GLPI identifier. Update, add, remove, and
delete operations return `None` and raise on error.

The client only forwards fields that you set explicitly on the model. It does
not inject package-owned defaults for ticket status, priority, type, or
category. If your GLPI workflow requires any of those values, set them on
`GlpiTicket` before calling `create_ticket()` or `update_ticket()`.
`create_ticket()` requires a non-empty ticket `name`.

`GlpiTicket` uses the GLPI ticket field names directly, including `id`,
`status`, `type`, `category`, `location`, `date_creation`, `date_mod`,
`date_close`, `user_recipient`, `user_editor`, and `team`.

When you request extra ticket fields that do not map to typed `GlpiTicket`
attributes, the package preserves them in `ticket.extra_payload` instead of
dropping them. This keeps the modeled fields typed while still exposing the raw
requested GLPI keys through a public field.

```python
tickets = glpi.search_ticket_records(
    query='status.id=in=(1,2)',
    fields=("resolution_date", "date_solve"),
)

first_ticket = tickets[0]
print(first_ticket.extra_payload["resolution_date"])
print(first_ticket.extra_payload["date_solve"])
```

## Entities

Use `search_entities()` when you need typed entity lookup from the public
package root.

```python
from glpi_python_client import GlpiEntity

entities = glpi.search_entities(
    rsql_filter='name=like=*novahe*',
    limit=50,
    start=0,
)

for entity in entities:
    print(entity.entity_id, entity.name, entity.complete_name)
```

Unmodeled entity payload keys are preserved in `GlpiEntity.extra_payload`.

## Models and Content Formatting

Public GLPI objects are field-validated Pydantic models. Create and update GLPI
data with `GlpiTicket`, `GlpiFollowup`, `GlpiSolution`, `GlpiDocument`,
`GlpiUser`, and `GlpiLocation` instead of passing raw dictionaries through
application code.

Ticket descriptions, followups, tasks, and solutions use Markdown in Python.
When data is fetched from GLPI, HTML is converted to Markdown before it is stored
on the model. When data is sent to GLPI, Markdown is rendered to HTML for the API
payload:

```python
ticket = GlpiTicket(
    name="Laptop cannot join corporate Wi-Fi",
    content=(
        "User sees **certificate rejected** during 802.1X authentication.\n"
        "- Device: Latitude 7450\n"
        "- Location: Paris office"
    ),
)
ticket_id = glpi.create_ticket(ticket)
```

Document file content remains `bytes`, because uploads and downloads must
preserve the original binary content.

## Custom Payload Keys

If your GLPI instance expects plugin fields or instance-specific payload keys,
use the public `extra_payload` field on the model you send through the client.
The validated model fields stay typed, and `extra_payload` is merged into the
outgoing GLPI request body.

```python
from glpi_python_client import GlpiTicket

ticket = GlpiTicket(
    name="Access badge reader offline",
    content="Reader in **Paris / 3rd floor** is unreachable.",
    extra_payload={
        "_room_code": "PAR-3F-12",
        "_asset_tag": "BADGE-READER-044",
    },
)

ticket_id = glpi.create_ticket(ticket)
```

Replace `_room_code` and `_asset_tag` with the raw GLPI field names expected by
your own instance or plugin. This same `extra_payload` pattern works on the
other payload-backed public models as well.

Search and fetch operations return typed models:

```python
tickets = glpi.search_ticket_records(query='status.id=in=(1,2)')
ticket = glpi.get_ticket_record("123")
followups = glpi.get_followup_records("123")
tasks = glpi.get_task_records("123")
solutions = glpi.get_solution_records("123")
```

Public client methods accept GLPI identifiers as either `str` or `int` and
normalize them into request paths as needed.

## Tasks And Duration Statistics

Use `search_task_records()` for global task searches and `get_task_durations()`
when you need aggregated duration reports.

```python
tasks = glpi.search_task_records(
    query='date=ge=2026-01-01;date=le=2026-01-31',
    fields=("id", "tickets_id", "users_id", "actiontime", "date", "content"),
    sort="date:desc",
)

summary = glpi.get_task_durations(
    start_date="2026-01-01",
    end_date="2026-01-31",
    entity_name="Novahe",
    return_task_details=True,
)

print(summary["total_duration"])
print(summary["duration_by_user"])
```

`GlpiTask` keeps typed fields such as `ticket_id`, `user_id`, `duration`,
`date`, and `entity`. Additional task payload keys remain available through
`GlpiTask.extra_payload`.

## Ticket Statistics And User Activity

Public enums keep the GLPI numeric constants at the package root and can be
used directly in filters.

```python
from glpi_python_client import GlpiPriority, GlpiTicketStatus, GlpiTicketType

open_ticket_query = GlpiTicketStatus.NEW.rsql_equals("status")
request_query = GlpiTicketType.REQUEST.rsql_equals("type")

stats = glpi.get_ticket_statistics(
    entity_name="Novahe",
    start_date="2026-01-01",
    end_date="2026-01-31",
    extra_filter=f"{open_ticket_query};{request_query}",
)

activity = glpi.get_user_activity(
    email="jane.doe@example.com",
    start_date="2026-01-01",
    end_date="2026-01-31",
)

print(stats["entities"])
print(activity["users"])
```

The statistics output groups counts by entity, status, priority, and type. The
activity output groups requester counts, technician counts, and nested task
duration summaries by user.

## Ticket Context

Use `get_ticket_context()` when you need the core ticket together with the
common timeline and document records in one public object.

```python
bundle = glpi.get_ticket_context("123")

print(bundle.ticket.id)
print(len(bundle.tasks), len(bundle.followups), len(bundle.solutions))
print(len(bundle.documents))
```

## Users and Locations

```python
from glpi_python_client import GlpiLocation, GlpiUser

user_id = glpi.create_user(
    GlpiUser(email="jane@example.com", firstname="Jane", realname="Doe")
)
location_id = glpi.create_location(GlpiLocation(name="Paris office"))
glpi.delete_user(user_id)
glpi.delete_location(location_id)
```

`create_user()` requires at least one usable identity value on `GlpiUser`.
`create_location()` requires a non-empty location `name`.

## Documents

Document upload uses the legacy v1 API credentials when your GLPI instance
requires them:

- `v1_base_url` is optional and only needed when your GLPI instance exposes
    document upload through a separate v1 endpoint such as `/api.php/v1` or
    `/apirest.php`.
- `v1_user_token` is required when `v1_base_url` is supplied.
- `v1_app_token` is optional when that v1 endpoint does not require an app
    token.

```python
from glpi_python_client import GlpiDocument

uploaded = glpi.upload_document_to_ticket(
    GlpiDocument(
        ticket_id=123,
        filename="diagnostic.txt",
        content=b"network trace",
        mime_type="text/plain",
    )
)
if uploaded.document_id is not None:
    glpi.delete_document(uploaded.document_id)
```

## Error Handling

Transport helpers raise `ValueError` for non-successful GLPI responses that
cannot be represented as a normal return value. Retriable server-side errors are
retried with `tenacity` before surfacing to the caller.
