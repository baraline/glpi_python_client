---
name: glpi-client-setup
description: "Create and configure the synchronous glpi_python_client.GlpiClient or the asynchronous glpi_python_client.AsyncGlpiClient, including from_env, OAuth credential pairs, entity/profile headers, SSL settings, and the optional legacy v1 document-upload session. Use before calling GLPI APIs or when the user asks how to connect to GLPI with glpi_python_client."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to a GLPI v2 API, and valid GLPI credentials."
metadata:
  package: glpi-python-client
  version: "0.4.0"
---

# GLPI Client Setup

The package exposes two clients with identical endpoint surfaces:

- `glpi_python_client.GlpiClient` — synchronous, blocking client. Use it from
  scripts, CLI tools, or any code that is not already running inside an
  event loop.
- `glpi_python_client.AsyncGlpiClient` — asynchronous facade. Each method
  is a coroutine that dispatches the underlying blocking call on a worker
  thread (`asyncio.to_thread` by default, or a caller-supplied
  `concurrent.futures.Executor`). Use it when an event loop is already
  running or when you want concurrent fan-out via `asyncio.gather`.

Both clients share the same method names and signatures, including
`from_env`, OAuth handling, retry behaviour, and the optional v1
document-upload fallback. Pick the one matching the runtime model and
keep usage consistent within a single application.

Use the sync client as a context manager: `with GlpiClient(...) as
client`. Use the async client as an async context manager: `async with
AsyncGlpiClient(...) as client`. When the client outlives one block,
call `client.close()` (or `await client.close()`) when finished.

## Procedure

1. Pick the client class: `GlpiClient` for synchronous code,
   `AsyncGlpiClient` for asynchronous code.
2. Decide whether credentials come from environment variables or
   explicit arguments.
3. Provide `glpi_api_url` for the GLPI v2 API (typically ending in
   `/api.php/v2`).
4. Provide at least one complete authentication pair: `client_id`/
   `client_secret`, `username`/`password`, or both pairs together.
5. Add `glpi_entity`, `glpi_profile`, and `entity_recursive=True` only
   when the operation must run in a specific GLPI scope.
6. Add `v1_base_url` and `v1_user_token` only when binary document
   uploads are needed (`upload_document`). `v1_app_token` is optional.
7. Keep `verify_ssl=True` unless the user explicitly confirms a test or
   internal endpoint that cannot validate TLS.
8. For the async client only, optionally pass `executor=` a
   `concurrent.futures.ThreadPoolExecutor` to bound worker threads.

## Environment Defaults

`GlpiClient.from_env()` and `AsyncGlpiClient.from_env()` read the same
`GLPI_`-prefixed settings:

- `GLPI_API_URL`
- `GLPI_CLIENT_ID` and `GLPI_CLIENT_SECRET`
- `GLPI_USERNAME` and `GLPI_PASSWORD`
- `GLPI_ENTITY`, `GLPI_PROFILE`, `GLPI_ENTITY_RECURSIVE`
- `GLPI_LANGUAGE`, `GLPI_VERIFY_SSL`, `GLPI_AUTH_TOKEN_REFRESH`
- `GLPI_V1_BASE_URL`, `GLPI_V1_USER_TOKEN`, `GLPI_V1_APP_TOKEN`

Pass keyword overrides to replace selected environment values.

## Examples

Explicit setup, synchronous:

```python
from glpi_python_client import GlpiClient


def main() -> None:
    with GlpiClient(
        glpi_api_url="https://glpi.example.com/api.php/v2",
        client_id="oauth-client-id",
        client_secret="oauth-client-secret",
        username="api-user",
        password="api-password",
        glpi_entity=1,
        glpi_profile=4,
    ) as glpi:
        tickets = glpi.search_tickets("status==1", limit=10)


main()
```

Explicit setup, asynchronous:

```python
import asyncio

from glpi_python_client import AsyncGlpiClient


async def main() -> None:
    async with AsyncGlpiClient(
        glpi_api_url="https://glpi.example.com/api.php/v2",
        client_id="oauth-client-id",
        client_secret="oauth-client-secret",
        username="api-user",
        password="api-password",
        glpi_entity=1,
        glpi_profile=4,
    ) as glpi:
        tickets = await glpi.search_tickets("status==1", limit=10)


asyncio.run(main())
```

Environment setup, synchronous:

```python
from glpi_python_client import GlpiClient

with GlpiClient.from_env() as glpi:
    tickets = glpi.search_tickets("status==1")
```

Environment setup, asynchronous:

```python
from glpi_python_client import AsyncGlpiClient

async with AsyncGlpiClient.from_env() as glpi:
    tickets = await glpi.search_tickets("status==1")
```

Document-upload setup (works on either client):

```python
with GlpiClient.from_env(
    v1_base_url="https://glpi.example.com/apirest.php",
    v1_user_token="legacy-user-token",
) as glpi:
    ...
```

## Gotchas

- The two clients share the same endpoint surface; the only difference
  is whether methods are blocking or coroutines. Do not mix them in the
  same application unless you genuinely need both runtime models.
- The package no longer exports `GLPIV1Session`. Configure
  `v1_base_url`/`v1_user_token` on the client and call
  `upload_document` instead.
- Use `glpi_api_url` for the v2 API; `v1_base_url` is only for the
  document-upload fallback.
- Closing the client matters because it owns one or two HTTP sessions
  plus an OAuth token manager. Prefer the context-manager form.
- A shared `threading.Lock` serialises OAuth token acquisition, so it
  is safe to launch concurrent `asyncio.gather` fan-outs on
  `AsyncGlpiClient` even before the token has been fetched once.
