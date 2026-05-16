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

It currently focuses on ticket-centric workflows and exposes a single
asynchronous high-level client built on top of the GLPI v2 REST API.
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

```python
import asyncio

from glpi_python_client import GlpiClient, PostTicket


async def main() -> None:
    async with GlpiClient(
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

If your application already provides `GLPI_` environment variables,
`GlpiClient.from_env()` is also available.

### Calling from synchronous code
For now, I provide only an async client, but if necessary, could
duplicate the code to make a sync client. Until then you can make
it works from sync programs through
`asyncio.run`. Wrap the calls in a coroutine and execute it once:

```python
import asyncio

from glpi_python_client import GlpiClient


def fetch_open_tickets() -> list[int]:
    async def _run() -> list[int]:
        async with GlpiClient.from_env() as glpi:
            tickets = await glpi.search_tickets("status==1", limit=10)
            return [ticket.id for ticket in tickets]

    return asyncio.run(_run())


if __name__ == "__main__":
    print(fetch_open_tickets())
```

For long-lived sync services that need many calls, run a dedicated
event loop on a background thread and dispatch with
`asyncio.run_coroutine_threadsafe`. See the
[user guide](https://glpi-python-client.readthedocs.io/en/latest/user_guide.html#calling-the-client-from-synchronous-code)
for the full pattern.

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
