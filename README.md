# glpi-python-client

[![CI](https://github.com/baraline/glpi_python_client/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/baraline/glpi_python_client/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/baraline/glpi_python_client/branch/main/graph/badge.svg)](https://codecov.io/gh/baraline/glpi_python_client)
[![License](https://img.shields.io/github/license/baraline/glpi_python_client)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://github.com/baraline/glpi_python_client)
[![Docs](https://readthedocs.org/projects/glpi-python-client/badge/?version=latest)](https://glpi-python-client.readthedocs.io/en/latest/)

`glpi-python-client` is a typed Python client for the GLPI REST API.

The goal is to let GLPI integrations work with domain objects instead of raw
JSON payloads. The package exposes Pydantic models for tickets, users,
followups, documents, locations, and related records, while converting GLPI
HTML content into Markdown for Python-side workflows and rendering Markdown
back to HTML for outgoing payloads.

It currently focuses on ticket-centric workflows and exposes two high-level
clients built on top of the GLPI v2 REST API:

- `GlpiClient` — synchronous, blocking client (single source of truth for
  endpoint behaviour).
- `AsyncGlpiClient` — asynchronous facade that wraps every synchronous
  method into a coroutine and dispatches it to a worker thread.

Note that all integration tests using this package are made on GLPI 11.
I cannot make any guarantee of the behaviour on previous versions.

While the package is preparing for 1.0, alot of potential breaking change might happen between versions. A deprecation policy will be put in place once 1.0 is out and the package have been stabilized.

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

Create a client with your GLPI v2 API URL and at least one complete auth pair:

- `client_id` and `client_secret`
- `username` and `password`
- both pairs together

### Synchronous client

```python
from glpi_python_client import GlpiClient, PostTicket

with GlpiClient(
    glpi_api_url="https://glpi.example.com/api.php/v2",
    client_id="oauth-client-id",
    client_secret="oauth-client-secret",
    username="api-user",
    password="api-password",
) as glpi:
    ticket_id = glpi.create_ticket(
        PostTicket(
            name="Printer issue",
            content="The printer is not reachable from the office network.",
        )
    )
    ticket = glpi.get_ticket(ticket_id)
    print(ticket.id, ticket.name)
```

### Asynchronous client

```python
import asyncio

from glpi_python_client import AsyncGlpiClient, PostTicket


async def main() -> None:
    async with AsyncGlpiClient(
        glpi_api_url="https://glpi.example.com/api.php/v2",
        client_id="oauth-client-id",
        client_secret="oauth-client-secret",
        username="api-user",
        password="api-password",
    ) as glpi:
        ticket_id = await glpi.create_ticket(
            PostTicket(
                name="Printer issue",
                content="The printer is not reachable from the office network.",
            )
        )
        ticket = await glpi.get_ticket(ticket_id)
        print(ticket.id, ticket.name)


asyncio.run(main())
```

`GlpiClient.from_env()` and `AsyncGlpiClient.from_env()` are also available
when the credentials are already exposed as `GLPI_`-prefixed environment
variables.

### Sync or async?

Both clients expose the exact same endpoint surface and accept the same
constructor arguments. The async client is a thin facade that wraps each
synchronous method into a coroutine dispatched to a worker thread via
`asyncio.to_thread` (or a caller-supplied `concurrent.futures.Executor`).
A shared `threading.Lock` serialises OAuth token acquisition so concurrent
`asyncio.gather(...)` fan-outs cannot race. Pick `GlpiClient` for plain
scripts, CLI tools, and synchronous services; pick `AsyncGlpiClient` when
your application already runs an event loop or when you need concurrent
fan-out (the aggregated `get_ticket_context` and per-ticket
`get_task_statistics` helpers use `asyncio.gather` on the async client).

## Documentation

- [Hosted documentation](https://glpi-python-client.readthedocs.io/en/latest/)
- [API reference](https://glpi-python-client.readthedocs.io/en/latest/api_reference.html)
- [Installation guide](https://glpi-python-client.readthedocs.io/en/latest/installation.html)
- [Development guide](https://glpi-python-client.readthedocs.io/en/latest/development_rtd.html)

To build the Sphinx documentation locally:

```bash
python -m pip install -e .[docs]
python -m sphinx -b html docs docs/_build/html
```
