# Development Guide

## Local Setup

Create a virtual environment and install the package with development dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
python -m pre_commit install
```

The repository ships a root `.pre-commit-config.yaml` that runs Ruff on each
commit. The lint hook applies safe fixes first, then Ruff formats the touched
files.

## Checks

Run these before publishing or opening a pull request:

```bash
python -m pre_commit run --all-files
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

- `glpi_python_client.__init__` exposes the public import surface,
  including both client classes and the Pydantic models.
- `glpi_python_client._sync.clients.client.GlpiClient` is the
  synchronous, blocking client. It is the single source of truth for
  endpoint behaviour: each public method lives on one of the sync
  endpoint mixins under `glpi_python_client._async.clients.api.*` and
  `glpi_python_client._async.clients.custom.*`.
- `glpi_python_client._async.clients.client.AsyncGlpiClient` is the
  asynchronous facade. It inherits the same endpoint mixins and uses
  `glpi_python_client._async._concurrency` to wrap
  every inherited public sync method into a coroutine dispatched on a
  worker thread (`asyncio.to_thread` by default, or a caller-supplied
  `concurrent.futures.Executor`).
- `glpi_python_client._async.clients.commons` holds the reusable building
  blocks shared by every endpoint mixin: configuration helpers
  (`_config`), constants (`_constants`), errors (`_errors`), filters
  (`_filters`), HTTP helpers (`_http`), payload builders (`_payloads`),
  and the `TransportMixin` (`_transport`). The transport serialises OAuth
  token acquisition with the lock from `_async/_concurrency.py`, so
  concurrent callers cannot race the token manager.
- `glpi_python_client._async.clients.api.*` contains the contract-aligned
  endpoint mixins, grouped by GLPI subtree (administration, assistance,
  assistance/timeline, dropdowns, management, knowledgebase, plugins).
  Each mixin is written once, in the async tree. (Historically some had
  hand-written async overrides needed
  because their synchronous bodies call a sibling public method through
  `self` (see the `clients.custom` entry below for the other reason a
  method needs one).
- `glpi_python_client._async.clients.custom` contains custom helpers built on
  top of the API mixins. Each helper has a synchronous implementation
  (`_ticket_context.py`, `_statistics.py`) plus an async override
  (`_ticket_context_async.py`, `_statistics_async.py`) that fans the
  underlying calls out concurrently with `asyncio.gather`. That is one
  of two reasons a method needs a hand-written async override; the
  other — a synchronous body calling a sibling public method through
  `self` — is why `clients.api.knowledgebase` and `clients.api.plugins`
  also ship one (see above).
- `glpi_python_client._async.auth._v1_session` contains the legacy v1
  session used for binary document uploads.
- `glpi_python_client.models` contains typed request and response
  models.
- `glpi_python_client.content` handles HTML/Markdown conversion for
  ticket descriptions, followups, tasks, and solutions.
- `glpi_python_client.testing` exposes `make_client` and
  `make_async_client` factories that produce in-memory clients with no
  real HTTP plumbing for downstream test suites.
- `docs` contains the Read the Docs/Sphinx documentation source.
- `skills` contains contributor-facing Agent Skills for repository
  workflows. The source distribution includes them for source consumers
  and contributors, but the wheel still installs only the
  `glpi_python_client` runtime package.

## Adding Endpoints

1. Add or extend a model in `glpi_python_client.models`.
2. Add the client method on the matching endpoint mixin under
   `glpi_python_client/_async/clients/api/**` (or `.../custom/**` for
   derived helpers), as an `async def`. Then run `python
   unasync_build.py` to regenerate `glpi_python_client/_sync/`, and
   commit both. **Never edit `_sync/` by hand** — CI regenerates it and
   fails on any difference.

   Write the method once. There is no parallel async mixin to keep in
   step: if it needs concurrent fan-out, call `gather` from
   `glpi_python_client/_async/_concurrency.py`, which runs the calls
   concurrently on the async surface and sequentially on the generated
   one, from the same source line.
3. Put reusable endpoint names, payload builders, response handling, or
   pagination logic in the focused
   `glpi_python_client._async.clients.commons` helper module named for that
   responsibility.
4. Add unit tests for payload serialization, response parsing, and
   client behavior. The parity test in
   `glpi_python_client/clients/tests/test_parity.py` will fail if the
   sync and async surfaces diverge, and
   `glpi_python_client/clients/tests/test_async_selfcall_guard.py` will
   fail if a public method reaches another public method through `self`
   without a hand-written async override.
5. Document the new workflow in `docs/user_guide.rst` or the README.

Keep organization-specific defaults outside the package core.
Applications can map their own entities, profiles, and categories
before calling the client.
