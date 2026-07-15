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
- `glpi_python_client.clients.sync_client.GlpiClient` is the
  synchronous, blocking client. It is the single source of truth for
  endpoint behaviour: each public method lives on one of the sync
  endpoint mixins under `glpi_python_client.clients.api.*` and
  `glpi_python_client.clients.custom.*`.
- `glpi_python_client.clients.async_client.AsyncGlpiClient` is the
  asynchronous facade. It inherits the same endpoint mixins and uses
  `glpi_python_client.clients.commons._async_bridge.AsyncBridge` to wrap
  every inherited public sync method into a coroutine dispatched on a
  worker thread (`asyncio.to_thread` by default, or a caller-supplied
  `concurrent.futures.Executor`).
- `glpi_python_client.clients.commons` holds the reusable building
  blocks shared by every endpoint mixin: configuration helpers
  (`_config`), constants (`_constants`), errors (`_errors`), filters
  (`_filters`), HTTP helpers (`_http`), payload builders (`_payloads`),
  the synchronous `TransportMixin` (`_transport`), and the
  `AsyncBridge` (`_async_bridge`). A shared `threading.Lock` in the
  transport serialises OAuth token acquisition so concurrent
  `asyncio.gather` fan-outs on the async client cannot race.
- `glpi_python_client.clients.api.*` contains the contract-aligned
  endpoint mixins, grouped by GLPI subtree (administration, assistance,
  assistance/timeline, dropdowns, management, knowledgebase, plugins).
  Most are synchronous; `knowledgebase/_article_async.py` and
  `plugins/_fields_async.py` are hand-written async overrides needed
  because their synchronous bodies call a sibling public method through
  `self` (see the `clients.custom` entry below for the other reason a
  method needs one).
- `glpi_python_client.clients.custom` contains custom helpers built on
  top of the API mixins. Each helper has a synchronous implementation
  (`_ticket_context.py`, `_statistics.py`) plus an async override
  (`_ticket_context_async.py`, `_statistics_async.py`) that fans the
  underlying calls out concurrently with `asyncio.gather`. That is one
  of two reasons a method needs a hand-written async override; the
  other — a synchronous body calling a sibling public method through
  `self` — is why `clients.api.knowledgebase` and `clients.api.plugins`
  also ship one (see above).
- `glpi_python_client.auth._v1_session` contains the legacy v1
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
2. Add the client method on the matching **synchronous** endpoint mixin
   under `glpi_python_client.clients.api.*` (or
   `glpi_python_client.clients.custom.*` for derived helpers). The
   async client picks the new method up automatically through the
   `AsyncBridge` — do not duplicate the method on a parallel async
   mixin unless you genuinely need concurrent fan-out (`asyncio.gather`)
   inside the method body, **or** the method calls a sibling public
   method through `self` (directly, or transitively via a private
   helper): the bridge wraps that sibling into a coroutine, so the
   un-awaited call silently drops instead of running. The guard in step
   4 fails the suite if you miss this.
3. Put reusable endpoint names, payload builders, response handling, or
   pagination logic in the focused
   `glpi_python_client.clients.commons` helper module named for that
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
