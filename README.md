# glpi-python-client

[![CI](https://github.com/baraline/glpi_python_client/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/baraline/glpi_python_client/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/baraline/glpi_python_client)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://github.com/baraline/glpi_python_client)
[![Docs](https://img.shields.io/badge/docs-Sphinx-blue)](docs/)

`glpi-python-client` is a typed Python client for GLPI ITSM APIs.

The goal is to let GLPI integrations work with domain objects instead of raw
JSON payloads. The package exposes Pydantic models for tickets, users,
followups, documents, locations, and related records, while converting GLPI
HTML content into Markdown for Python-side workflows and rendering Markdown
back to HTML for outgoing payloads.

It currently focuses on ticket-centric workflows and exposes matching sync and
async high-level clients.

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

Create a client with your GLPI API URL and at least one complete auth pair:

- `client_id` and `client_secret`
- `username` and `password`
- both pairs together

```python
from glpi_python_client import GlpiClient, GlpiTicket

with GlpiClient(
    glpi_api_url="https://glpi.example.com/api.php",
    client_id="oauth-client-id",
    client_secret="oauth-client-secret",
    username="api-user",
    password="api-password",
) as glpi:
    ticket_id = glpi.create_ticket(
        GlpiTicket(
            name="Printer issue",
            content="The printer is not reachable from the office network.",
            urgency=3,
            impact=3,
        )
    )
    ticket = glpi.get_ticket_record(ticket_id)

    print(ticket.id)
    print(ticket.content)
```

Async code uses the same model layer and nearly the same API surface:

```python
from glpi_python_client import AsyncGlpiClient

async with AsyncGlpiClient(
    glpi_api_url="https://glpi.example.com/api.php",
    client_id="oauth-client-id",
    client_secret="oauth-client-secret",
) as glpi:
    tickets = await glpi.search_ticket_records(query='status.id=in=(1,2)')
```

If your application already provides `GLPI_` environment variables,
`GlpiClient.from_env()` and `AsyncGlpiClient.from_env()` are also available.

## Documentation

- [Usage guide](docs/usage.md)
- [API reference](docs/api_reference.rst)
- [Development guide](docs/development.md)
- [Publishing checklist](docs/publishing.md)

To build the Sphinx documentation locally:

```bash
python -m pip install -e .[docs]
python -m sphinx -b html docs docs/_build/html
```
