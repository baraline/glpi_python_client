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

- `GlpiClient` — synchronous, blocking client.
- `AsyncGlpiClient` — asynchronous client doing real non-blocking I/O on the
  event loop.

Neither wraps the other. The async tree is hand-written and the sync one is
generated from it, so the two surfaces cannot drift apart.

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
    server_timezone="Europe/Paris",
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
        server_timezone="Europe/Paris",
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
constructor arguments, because both are generated from one source: the
async tree is hand-written and the sync one is produced from it by a build
step that strips `async`/`await`. `AsyncGlpiClient` performs real
non-blocking I/O on the event loop — there is no worker thread and no
executor — and `GlpiClient` performs real blocking I/O with no coroutine
scheduling. An auth lock serialises OAuth token acquisition on both
surfaces, so concurrent fan-outs cannot race.

Pick `GlpiClient` for plain scripts, CLI tools, and synchronous services;
pick `AsyncGlpiClient` when your application already runs an event loop or
when you need concurrent fan-out (the aggregated `get_ticket_context` and
per-ticket `get_task_statistics` helpers overlap their calls there, and run
them one after another on the sync client).

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

## Sponsoring & Professional services
The development of this package is indirectly supported by [Novahé](https://www.novahe.fr/) & [Constellation](https://www.constellation.fr/).

If you need professional help or services around GLPI, we offer consulting and engineering services to install, maintain or upgarde GLPI instance, as an [official GLPI partner](https://www.glpi-project.org/fr/new-glpi-silver-partner-in-france-novahe/).

