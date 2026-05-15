---
name: glpi-client-setup
description: "Create and configure the asynchronous glpi_python_client.GlpiClient, including from_env, OAuth credential pairs, entity/profile headers, SSL settings, and the optional legacy v1 document-upload session. Use before calling GLPI APIs or when the user asks how to connect to GLPI with glpi_python_client."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to a GLPI v2 API, and valid GLPI credentials."
metadata:
  package: glpi-python-client
  version: "0.3.0"
---

# GLPI Client Setup

The package exposes a single asynchronous client at the package root: `glpi_python_client.GlpiClient`. The synchronous client and the legacy `AsyncGlpiClient`/`GLPIV1Session` public surface are gone — the v1 endpoint is now an internal fallback used only by `upload_document`.

Use the client as an async context manager: `async with GlpiClient(...) as client`. When the client outlives one block, call `await client.close()` when finished.

## Procedure

1. Decide whether credentials come from environment variables or explicit arguments.
2. Provide `glpi_api_url` for the GLPI v2 API (typically ending in `/api.php/v2`).
3. Provide at least one complete authentication pair: `client_id`/`client_secret`, `username`/`password`, or both pairs together.
4. Add `glpi_entity`, `glpi_profile`, and `entity_recursive=True` only when the operation must run in a specific GLPI scope.
5. Add `v1_base_url` and `v1_user_token` only when binary document uploads are needed (`upload_document`). `v1_app_token` is optional.
6. Keep `verify_ssl=True` unless the user explicitly confirms a test or internal endpoint that cannot validate TLS.
7. Always `await` client methods inside an async function.

## Environment Defaults

`GlpiClient.from_env()` reads `GLPI_`-prefixed settings:

- `GLPI_API_URL`
- `GLPI_CLIENT_ID` and `GLPI_CLIENT_SECRET`
- `GLPI_USERNAME` and `GLPI_PASSWORD`
- `GLPI_ENTITY`, `GLPI_PROFILE`, `GLPI_ENTITY_RECURSIVE`
- `GLPI_LANGUAGE`, `GLPI_VERIFY_SSL`, `GLPI_AUTH_TOKEN_REFRESH`
- `GLPI_V1_BASE_URL`, `GLPI_V1_USER_TOKEN`, `GLPI_V1_APP_TOKEN`

Pass keyword overrides to replace selected environment values.

## Examples

Explicit setup:

```python
import asyncio

from glpi_python_client import GlpiClient


async def main() -> None:
    async with GlpiClient(
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

Environment setup:

```python
from glpi_python_client import GlpiClient

async with GlpiClient.from_env() as glpi:
    tickets = await glpi.search_tickets("status==1")
```

Document-upload setup:

```python
async with GlpiClient.from_env(
    v1_base_url="https://glpi.example.com/apirest.php",
    v1_user_token="legacy-user-token",
) as glpi:
    ...
```

## Gotchas

- Only one client class exists. There is no longer a `GLPIClient` (sync) or a separate `AsyncGlpiClient`; the public class is named `GlpiClient` and is async.
- The package no longer exports `GLPIV1Session`. Configure `v1_base_url`/`v1_user_token` on `GlpiClient` and call `upload_document` instead.
- Use `glpi_api_url` for the v2 API; `v1_base_url` is only for the document-upload fallback.
- Closing the client matters because it owns one or two HTTP sessions plus an OAuth token manager.
