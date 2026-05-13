---
name: glpi-client-setup
description: "Create and configure sync or async glpi-python-client clients, including from_env, OAuth credential pairs, entity/profile headers, SSL settings, and legacy v1 document-upload credentials. Use before calling GLPI APIs or when the user asks how to connect to GLPI with glpi_python_client."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, requests-compatible network access to a GLPI API, and valid GLPI credentials."
metadata:
  package: glpi-python-client
  version: "0.1.0"
---

# GLPI Client Setup

After the client refactor, keep imports on the stable package root: `glpi_python_client.GlpiClient` and `glpi_python_client.AsyncGlpiClient`. The implementation now lives in scoped sync, async, and common modules under `glpi_python_client.clients.v2`, but callers should not import those internal modules directly.

Use a context manager for one-shot work: `with GlpiClient(...)` or `async with AsyncGlpiClient(...)`. If the client outlives one block, call `close()` or `await close()` when finished.

## Procedure

1. Decide whether the workflow is synchronous or asynchronous and choose `GlpiClient` or `AsyncGlpiClient`.
2. Decide whether credentials come from environment variables or explicit arguments.
3. Provide `glpi_api_url` for the GLPI high-level API, usually ending in `/api.php`.
4. Provide at least one complete authentication pair: `client_id` with `client_secret`, `username` with `password`, or both pairs together.
5. Add `glpi_entity`, `glpi_profile`, and `entity_recursive=True` only when the operation must run in a specific GLPI scope.
6. Add `v1_base_url` and `v1_user_token` only when document upload or legacy v1 document linking is required. `v1_app_token` is optional.
7. Keep `verify_ssl=True` unless the user explicitly confirms a test or internal endpoint that cannot validate TLS.
8. In async code, use the same constructor arguments and public method names on `AsyncGlpiClient`, but `await` remote operations.

## Environment Defaults

`GlpiClient.from_env()` and `AsyncGlpiClient.from_env()` read `GLPI_`-prefixed settings by default:

- `GLPI_API_URL`
- `GLPI_CLIENT_ID` and `GLPI_CLIENT_SECRET`
- `GLPI_USERNAME` and `GLPI_PASSWORD`
- `GLPI_ENTITY`, `GLPI_PROFILE`, `GLPI_ENTITY_RECURSIVE`
- `GLPI_LANGUAGE`, `GLPI_VERIFY_SSL`
- `GLPI_V1_BASE_URL`, `GLPI_V1_USER_TOKEN`, `GLPI_V1_APP_TOKEN`

Pass keyword overrides to replace selected environment values.

## Examples

Explicit synchronous setup:

```python
from glpi_python_client import GlpiClient

with GlpiClient(
    glpi_api_url="https://glpi.example.com/api.php",
    client_id="oauth-client-id",
    client_secret="oauth-client-secret",
    username="api-user",
    password="api-password",
    glpi_entity=1,
    glpi_profile=4,
) as glpi:
    tickets = glpi.search_ticket_records(query='status.id=in=(1,2)')
```

Environment setup:

```python
from glpi_python_client import GlpiClient

with GlpiClient.from_env() as glpi:
    tickets = glpi.search_ticket_records(query='status.id=in=(1,2)')
```

Async environment setup:

```python
from glpi_python_client import AsyncGlpiClient

async with AsyncGlpiClient.from_env() as glpi:
    tickets = await glpi.search_ticket_records(query='status.id=in=(1,2)')
```

Document-upload setup:

```python
from glpi_python_client import GlpiClient

with GlpiClient.from_env(
    v1_base_url="https://glpi.example.com/apirest.php",
    v1_user_token="legacy-user-token",
) as glpi:
    ...
```

## Gotchas

- Do not require all four OAuth/user credentials. The package supports either complete pair or both pairs.
- Use `glpi_api_url` for the high-level API. `v1_base_url` is only for the legacy v1 document gateway.
- `AsyncGlpiClient` exposes the same constructor settings and `from_env()` mapping; use `async with` and `await` instead of importing internal async mixins.
- Legacy v1 configuration is not needed for ordinary ticket searches, ticket updates, followups, solutions, users, or locations.
- Closing the client matters because it owns one or two HTTP sessions.
