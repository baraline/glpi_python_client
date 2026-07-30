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
- `glpi_python_client/_async/` is the **only hand-written client tree**,
  and `glpi_python_client/_sync/` is generated from it by
  `unasync_build.py` and committed. Every endpoint method is therefore
  written exactly once, as an `async def`, and the sync client is a
  mechanical token transform of it. CI regenerates the tree and fails on
  any difference.
- `glpi_python_client._async.clients.client.AsyncGlpiClient` and its
  generated twin `glpi_python_client._sync.clients.client.GlpiClient` are
  composed from the same endpoint mixins. Neither wraps the other:
  the async client performs real non-blocking I/O and the sync one real
  blocking I/O.
- `glpi_python_client._async._concurrency` is the one module hand-written
  on *both* sides, because the two surfaces need primitives that differ
  in kind rather than in spelling: the auth lock is an `asyncio.Lock`
  against a `threading.Lock`, and `gather` is a real fan-out against
  plain sequential evaluation. Neither substitutes for the other — see
  the module for what breaks in each direction. Call `gather` from there
  for concurrent fan-out, never `asyncio.gather` directly, which unasync
  would leave intact and emit as broken sync code.
- `glpi_python_client._async.clients.commons` holds the reusable building
  blocks shared by every endpoint mixin: configuration helpers
  (`_config`), constants (`_constants`), filters (`_filters`), HTTP
  helpers (`_http`), payload builders (`_payloads`), and the
  `TransportMixin` (`_transport`). The transport serialises OAuth token
  acquisition with the lock from `_concurrency`, so concurrent callers
  cannot race the token manager.
- `glpi_python_client._errors` defines the public exception hierarchy
  (`GlpiError` and its subclasses), re-exported from the package root.
- `glpi_python_client._async.clients.api.*` contains the contract-aligned
  endpoint mixins, grouped by GLPI subtree (administration, assistance,
  assistance/timeline, dropdowns, management, knowledgebase, plugins).
- `glpi_python_client._async.clients.custom` contains helpers built on top
  of the API mixins (`_ticket_context.py`, `_statistics.py`). Their
  independent calls go through `gather`, so one implementation fans out
  on the async surface and runs sequentially on the generated one.
- `glpi_python_client._async.auth._v1_session` contains the legacy v1
  session used for binary document uploads and the `Fields` plugin.
- `glpi_python_client.models` contains typed request and response
  models.
- `glpi_python_client.content` handles HTML/Markdown conversion for
  ticket descriptions, followups, tasks, and solutions.
- `glpi_python_client.testing` exposes `make_client` and
  `make_async_client` factories that produce in-memory clients with no
  real HTTP plumbing for downstream test suites, plus the shared
  `DEFAULT_CLIENT_CONFIG` and the fake response classes. Its `tests/`
  subpackage holds this repository's own cross-cutting suites.
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
4. Add unit tests in the `tests/` package beside the module you changed —
   `_async/clients/api/assistance/tests/test_ticket.py` for a change to
   `_async/clients/api/assistance/_ticket.py`. Write them as `async def`,
   then run `python unasync_build.py` and commit both trees. The
   generated twins exercise the sync client, so one source covers both
   surfaces.

   Import the client factory from `glpi_python_client._async._testing`,
   not from `glpi_python_client.testing`: the former is generated, so it
   returns an `AsyncGlpiClient` in the source and a `GlpiClient` in the
   twin. The latter is published API and always returns what its name
   says.

   Any stub replacing an awaited internal must be a named `async def`, not
   a `lambda` — unasync cannot rewrite a lambda into a coroutine function.

   Two suites cover what colocated tests cannot reach.
   `glpi_python_client/testing/tests/test_unasync_codegen.py` holds the
   invariants the CI diff gate is blind to — a token collision is
   deterministic, so regeneration reproduces it and the diff stays clean.
   `glpi_python_client/_async/tests/test_concurrency.py` and its `_sync`
   twin cover what codegen cannot: that a method actually awaits, that
   contending tasks do not deadlock on the auth lock, that `gather`
   genuinely overlaps its arguments on the async side, and that the sync
   twin's own lock excludes and its sequential `gather` preserves order.
   Add to it whenever a change is only observable once `async`/`await`
   are real.
5. Document the new workflow in `docs/user_guide.rst` or the README.

Keep organization-specific defaults outside the package core.
Applications can map their own entities, profiles, and categories
before calling the client.
