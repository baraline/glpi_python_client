# Development Guide

## Local Setup

Create a virtual environment and install the package with development dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

## Checks

Run these before publishing or opening a pull request:

```bash
python -m pytest
python -m ruff check .
python -m mypy glpi_python_client
python -m sphinx -b html docs docs/_build/html
python -m build
python -m vulture glpi_python_client --min-confidence 80
```

If your global Python environment has broken pytest plugins, run the suite with
plugin autoload disabled:

```bash
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
python -m pytest
```

## Package Layout

- `glpi_python_client.__init__` exposes the public import surface.
- `glpi_python_client.clients.api_v2_client.GlpiClient` owns synchronous API
  configuration, authentication, context-manager cleanup, and the small
  user/location/document provisioning surface.
- `glpi_python_client.clients.async_api_v2_client.AsyncGlpiClient` owns the
  matching awaitable client surface and keeps blocking requests behind
  `asyncio.to_thread()` boundaries.
- `glpi_python_client.clients.v2` contains the internal v2 implementation
  packages.
- `glpi_python_client.clients.v2.common` holds reusable setup, endpoint,
  request, pagination, payload, filter, and error helpers shared by both
  execution models.
- `glpi_python_client.clients.v2.sync` contains the synchronous endpoint mixins:
  `transport`, `tickets`, `timeline`, `documents`, `team`, and `directory`.
  `sync.api` assembles those mixins.
- `glpi_python_client.clients.v2.async_` contains the matching asynchronous
  endpoint mixins and keeps `asyncio.to_thread()` at the blocking request and
  v1-session boundaries. `async_.api` assembles those mixins.
- `glpi_python_client.clients._shared` is a compatibility module that re-exports
  the scoped v2 helper modules for older internal imports.
- `glpi_python_client.clients.api_v1_session` contains the legacy v1 session
  used for document operations.
- `glpi_python_client.models` contains typed request and response models.
- `glpi_python_client.content.records` is a compatibility package for raw GLPI
  payload conversion.
- `glpi_python_client.content.records.core` contains shared normalization,
  scalar coercion, nested-reference parsing, and timeline document-link
  helpers.
- `glpi_python_client.content.records.parsers` contains model-specific parsers
  for tickets, timeline items, documents, team members, users, and locations.
- `docs` contains the Read the Docs/Sphinx documentation source.
- `skills` contains contributor-facing Agent Skills for repository workflows.
  The source distribution includes them for source consumers and contributors,
  but the wheel still installs only the `glpi_python_client` runtime package.

## Adding Endpoints

1. Add or extend a model in `glpi_python_client.models`.
2. Add response parsing in the matching
  `glpi_python_client.content.records.parsers` module when the endpoint returns
  structured data, and put shared parsing helpers in
  `glpi_python_client.content.records.core` only when multiple parsers need
  them.
3. Add the client method in the matching
  `glpi_python_client.clients.v2.sync` module and the matching
  `glpi_python_client.clients.v2.async_` module when applicable.
4. Put reusable endpoint names, payload builders, response handling, or
  pagination logic in the focused `glpi_python_client.clients.v2.common`
  helper module named for that responsibility.
5. Add tests for payload serialization, response parsing, and client behavior.
6. Document the new workflow in `docs/usage.md` or the README.

Keep organization-specific defaults outside the package core. Applications can
map their own entities, profiles, and categories before calling the client.
