# Project Health Update Plan

Date created: 2026-05-12

This file tracks the cleanup and design work identified during the project
health review. Keep it updated as changes land: check completed tasks, add links
to issues or pull requests when they exist, and move newly discovered work into
the most relevant section.

## Status Legend

- `[ ]` Not started
- `[x]` Completed
- `Blocked:` Add a short note under the task explaining the blocker
- `Decision:` Add the chosen design decision under the task before implementation

## Current Baseline

- [x] Full test suite passes locally with `python -m pytest -q`.
- [x] Sphinx docs build passes locally with
  `python -m sphinx -W --keep-going -b html docs docs/_build/html`.
- [x] Ruff is clean with `python -m ruff check .`.
- [x] mypy is clean with `python -m mypy glpi_python_client`.
- [x] Dead-code scan is available in the development environment.
  - `vulture` is installed in the project virtual environment and the
    higher-confidence scan (`--min-confidence 80`) is clean.

## Guiding Principles

- Public signatures should communicate what callers must provide.
- `None` should mean a value is genuinely optional for the operation, not that
  the function will immediately fail later.
- Keep runtime validation for cross-field rules, environment-driven values, and
  remote API constraints that cannot be expressed by the signature alone.
- Prefer small, explicit compatibility breaks while the package is still alpha
  over carrying misleading public contracts.
- Add regression tests for every behavior that caused a health-review finding.

## Phase 1: Correctness And CI Recovery

- [x] Fix async client method resolution order.
  - Target: `glpi_python_client/clients/async_api_v2_client.py`.
  - Problem: `AsyncGlpiClient` currently inherits
    `AsyncGlpiProvisioningClientMixin` before `AsyncGlpiApiClientMixin`, so
    `_post_request()` resolves to the provisioning stub that raises
    `NotImplementedError`.
  - Expected change: put `AsyncGlpiApiClientMixin` before
    `AsyncGlpiProvisioningClientMixin`, matching the sync client pattern.
  - Tests to add: verify `_post_request` resolves to the async transport mixin,
    and cover at least one async create path without monkeypatching
    `_post_request` itself.

- [x] Close the legacy v1 HTTP session even when no v1 session token exists.
  - Target: `glpi_python_client/clients/api_v1_session.py`.
  - Problem: `GLPIV1Session.close()` returns early when `_session_token` is
    `None`, leaving the underlying `requests.Session` open for sessions that
    were constructed but never initialized.
  - Expected change: always close `_http`; only skip the `killSession` remote
    call when no token exists.
  - Tests to add: close-before-init, close-after-init, and idempotent close.

- [x] Fix Ruff failures.
  - Remove dead imports from `glpi_python_client/models/_base.py`.
  - Reformat imports and long lines in
    `glpi_python_client/models/glpi/_solution.py` and
    `glpi_python_client/testing/fixtures.py`.
  - Re-run `python -m ruff check .`.

- [x] Fix mypy failures without hiding them behind broad ignores.
  - Target: `glpi_python_client/content/records.py` and
    `glpi_python_client/models/glpi/_ticket.py`.
  - Use field-specific normalized reference rules instead of one overly broad
    reference contract.
  - Update the model types and helper functions so each reference field accepts
    the shapes it actually supports.
  - Update tests that assign mutation method results when those methods are
    intentionally typed as returning `None`.
  - Re-run `python -m mypy glpi_python_client`.

## Phase 2: Public API Argument Review

Goal: audit every public object and function argument so mandatory values are
mandatory in the signature, and optional values are optional because the object
or operation can work without them.

### Review Rules

- [x] Mark arguments as required when the object or function cannot work without
  them.
- [x] Keep arguments optional when they configure optional behavior or when a
  single model intentionally represents both input and response data.
- [x] Keep cross-field validation for credential pairs, v1 document upload
  configuration, and other rules that involve multiple arguments.
- [x] Update README, Sphinx docs, tests, and type expectations together with any
  public signature change.
- [x] Add a changelog note for each breaking public signature change.

### Concrete Argument Audit Items

- [x] Make `glpi_api_url` mandatory for `GlpiClient.__init__`.
  - Current shape: `glpi_api_url: str | None = None` followed by an immediate
    `ValueError` when omitted.
  - Preferred shape: `glpi_api_url: str` as a required keyword-only argument.
  - Rationale: the client cannot build the token endpoint or send API requests
    without it.
  - Follow-up: adjust tests that currently expect the constructor to accept a
    missing value and raise `ValueError`.

- [x] Make `glpi_api_url` mandatory for `AsyncGlpiClient.__init__`.
  - Mirror the sync client decision so both public clients share the same
    contract.

- [x] Review `GlpiClient.from_env()` and `AsyncGlpiClient.from_env()` error
  behavior after `glpi_api_url` becomes mandatory.
  - The env constructors may still read optional environment values internally,
    but should raise a clear missing-`API_URL` error before calling the required
    constructor.
  - Preserve explicit override behavior.

- [x] Review OAuth credential arguments on `GLPITokenManager`, `GlpiClient`, and
  `AsyncGlpiClient`.
  - `client_id` and `client_secret` should remain optional individually at the
    signature level only if pair validation stays clear and tested.
  - `username` and `password` should follow the same pair rule.
  - Confirm docs state the accepted combinations exactly once and link to that
    from both sync and async sections.
  - Decision: keep each credential optional at the signature level so callers can
    choose client credentials, password credentials, or both; enforce complete
    pairs in `GLPITokenManager` and document the accepted combinations.

- [x] Review legacy v1 document arguments.
  - `v1_base_url` and `v1_user_token` are optional for normal v2 usage.
    Reject partial v1 configuration; enable v1 document support only when both
    values are supplied.
  - `v1_app_token` can remain optional if empty app tokens are valid for target
    GLPI instances.
  - Decision: reject partial v1 configuration when only `v1_base_url` or only
    `v1_user_token` is supplied; keep `v1_app_token` optional.

- [x] Review operation identifiers.
  - Public methods such as `get_ticket_record(ticket_id)`,
    `get_followup_records(ticket_id)`, `get_document_record(document_id)`, and
    `download_document_content(document_id)` use the shared `GlpiId = str | int`
    convention across sync and async clients.
  - Decision: use the shared `GlpiId = str | int` alias across public sync and
    async ID arguments, including delete helpers and provisioning delete methods.

- [x] Review upload-only document requirements.
  - `GlpiDocument.ticket_id`, `filename`, and `content` are optional because the
    same model represents fetched document metadata and upload input.
  - Keep operation-level validation in `upload_document_to_ticket()`.
  - Do not introduce a dedicated upload input model in this cleanup.
  - Decision: keep `GlpiDocument` dual-purpose and retain operation-level
    validation for `ticket_id`, `filename`, and `content` during upload.

- [x] Review create/update model requirements.
  - `GlpiUser` creation requires at least a usable identity, but the response
    model can be partial.
  - `GlpiLocation` creation requires `name`, while fetched records also contain
    `location_id`.
  - `GlpiTicket` creation requires a non-empty `name`; document and test this
    package-level requirement.
  - Keep the dual-purpose models. Do not introduce separate create/update models
    in this cleanup.
  - Decision: keep dual-purpose models for now; enforce ticket and location
    create requirements at the operation boundary, and keep user identity
    validation in `GlpiUser.to_api_payload()`.

- [x] Review public exports.
  - Target: `glpi_python_client/__init__.py`, `glpi_python_client/clients/__init__.py`,
    and `glpi_python_client/models/__init__.py`.
  - Keep internal mixins and underscore helpers out of supported public exports.
  - Decision: keep supported clients and models exported; remove internal mixins
    and base helpers from package-level `__all__` surfaces.

## Phase 3: Design And Maintainability Improvements

- [x] Simplify the `clients` module without degrading async behavior.
  - Goal: reduce duplicated endpoint behavior between `GlpiClient` and
    `AsyncGlpiClient` while keeping the public client surface practical for GLPI
    API users.
  - Non-goal: introduce a large generic transport framework or complex data
    structure just to remove a few repeated lines.
  - Decision: keep `AsyncGlpiClient` async-shaped. Do not run whole paginated or
    multi-request sync workflows inside one worker thread. For now, continue to
    use `await asyncio.to_thread(...)` at the blocking request/session boundary.
    Do not add `httpx.AsyncClient` in this cleanup; treat true async transport
    as a separate future project backed by measured need.
  - Existing progress: shared environment/config parsing, request headers,
    request URLs, response finalization, response ID extraction, ticket search
    parameters, ticket pagination math, team-member payloads, document-upload
    validation, and several response-normalization helpers already live in
    `glpi_python_client.clients._shared`.

  - [x] Step 1: Freeze the public behavior before refactoring.
    - [x] Add a public-method inventory to this plan for `GlpiClient`,
      `AsyncGlpiClient`, and `GLPIV1Session`.
      - `GlpiClient`: `from_env`, `close`, context-manager methods,
        `search_ticket_records`, `get_ticket_record`, `get_followup_records`,
        `get_task_records`, `get_followup_attachment_document_ids`,
        `get_solution_attachment_document_ids`, `get_solution_records`,
        `get_document_records`, `get_document_record`,
        `download_document_content`, `delete_document`,
        `get_team_member_records`, `search_users`, `search_locations`,
        `create_ticket`, `update_ticket`, `delete_ticket`, `create_followup`,
        `update_followup`, `delete_followup`, `create_solution`,
        `delete_solution`, `add_team_member`, `remove_team_member`,
        `create_user`, `delete_user`, `create_location`, `delete_location`, and
        `upload_document_to_ticket`.
      - `AsyncGlpiClient`: async equivalents of the same public API, with
        `from_env`, `close`, and async context-manager methods.
      - `GLPIV1Session`: `get_sub_items`, `upload_document`,
        `link_document_to_ticket`, and `close`.
    - [x] Keep all current public method names and return types during this
      cleanup. The only public signature removal in scope is the dead
      `AsyncGlpiClient(batch_size=...)` constructor argument in Step 6.
    - [x] Add regression tests for representative sync and async paths:
      ticket search, ticket create/update/delete, followups, solutions, team
      members, users, locations, documents, context-manager cleanup, and v1
      upload.
    - [x] Replace tests that assert internal mixin resolution with tests that
      exercise the public method using the expected transport path.

  - [x] Step 2: Separate shared business rules from transport.
    - [x] Move deterministic behavior into `_shared`: endpoint assembly,
      payload construction, required-field checks, allowed status codes,
      response ID lookup, record-list extraction, pagination state transitions,
      and error-message formatting.
    - [x] Keep record conversion in `glpi_python_client.content.records`.
    - [x] Keep HTTP session ownership, locks, retries, and close behavior in the
      concrete sync/async clients.
    - [x] Inline one-off helpers when the helper name adds more indirection than
      clarity.
    - [x] Done when a public endpoint behavior change can usually be made in one
      shared helper plus one small sync/async transport call site.

  - [x] Step 3: Simplify the sync client first.
    - [x] Treat the sync request path as the baseline implementation because the
      current package transport is still `requests`.
    - [x] Extract shared helpers for the repeated create/update/delete patterns
      currently duplicated in sync and async methods.
    - [x] Keep the sync public methods readable without requiring users or
      maintainers to understand async machinery.
    - [x] Re-run the sync-focused client tests before touching the async mirror.

  - [x] Step 4: Rebuild async methods as thin async-shaped wrappers.
    - [x] Keep one `await` boundary per remote HTTP request in v2 methods.
    - [x] Use `await asyncio.to_thread(request_method, url, **kwargs)` for v2
      `requests` calls.
    - [x] Use `await asyncio.to_thread(v1_session.method, ...)` for legacy v1
      document operations that are still implemented with `requests`.
    - [x] Preserve async ticket pagination as an `AsyncIterator` that awaits one
      page at a time and yields each batch before fetching the next page.
    - [x] Avoid `await asyncio.to_thread(sync_client.search_ticket_records, ...)`
      for paginated or multi-request workflows because that would occupy one
      worker thread for the whole workflow and weaken cancellation/backpressure.
    - [x] Do not use whole-method `to_thread` wrappers for public client
      operations in this cleanup.

  - [x] Step 5: Remove inheritance-order fragility.
    - [x] Move `GlpiProvisioningClientMixin` public methods into `GlpiClient`.
    - [x] Move `AsyncGlpiProvisioningClientMixin` public methods into
      `AsyncGlpiClient`.
    - [x] Extract only deterministic provisioning payload and response helpers
      into `_shared`.
    - [x] Remove `_post_request()` and `_delete_request()` stubs that exist only
      to satisfy mixin type expectations.
    - [x] Delete MRO-specific regression tests once public-method transport
      tests cover the same behavior.
    - [x] Delete repository memory notes about mixin order after the mixins are
      removed.

  - [x] Step 6: Clean constructor and environment duplication.
    - [x] Extract one shared constructor helper for API URL normalization, SSL
      warning policy, `requests.Session` creation, OAuth manager setup, optional
      v1 session setup, and entity/profile/language assignment data.
    - [x] Keep lock creation and close behavior explicit because sync and async
      lifecycles differ.
    - [x] Fix `from_env()` override semantics so explicit `None` can clear an
      environment-derived optional value.
    - [x] Remove `AsyncGlpiClient(batch_size=...)` from the constructor.
    - [x] Add a changelog note for the removed async constructor argument.

  - [x] Step 7: Validate after each small slice.
    - [x] After changing shared helpers, run the focused clients tests:
      `python -m pytest glpi_python_client/clients/tests -q`.
    - [x] After changing public signatures or docs, run the docs checks listed
      in Phase 5.
    - [x] After removing mixins or moving helpers, run `python -m ruff check .`
      and `python -m mypy glpi_python_client`.
    - [x] Update this checklist as each slice lands; add new findings under the
      most relevant step instead of creating a separate cleanup list.

- [x] Document the async transport strategy.
  - Current async methods wrap blocking `requests` calls in `asyncio.to_thread`.
  - Decision: document the current async client as a compatibility wrapper around
    the shared `requests` transport; defer a true async transport until there is
    a concrete performance or integration need.
  - Do not add a new HTTP dependency during the clients-module simplification.

- [x] Centralize duplicated small parsing helpers.
  - Examples: `_optional_int`, `_optional_bool`, and `_optional_text` variants.
  - Avoid over-centralizing if local behavior genuinely differs by layer.
  - Decision: centralize the duplicated v2 client environment parsing helpers in
    `glpi_python_client.clients._shared`, while keeping record-parsing helpers
    local to `content.records` because their semantics are content-layer
    specific.

- [x] Add a safe RSQL/filter builder.
  - Target: `search_locations()` in sync and async clients.
  - Current behavior interpolates raw text into `name=like="*...*"`.
  - Add escaping tests for quotes, backslashes, wildcards, and empty input.

- [x] Rework document metadata enrichment.
  - Current `get_document_records()` performs one metadata request per linked
    document and swallows all metadata exceptions.
  - Log skipped metadata lookups with document IDs.
  - Keep `enrich_metadata: bool = True` as the public document-list metadata
    switch.
  - Do not implement batch metadata lookup until a supported GLPI batch endpoint
    is identified.
  - Decision: add `enrich_metadata` to sync and async document-list methods and
    log skipped per-document metadata lookups; keep batch lookup as future work
    because the current supported API path is per-document.

- [x] Clarify public and private modules.
  - Keep implementation helpers underscore-prefixed and out of public `__all__`.
  - Supported exports are the clients and models shown in the API reference.
  - Ensure `docs/api_reference.rst` reflects the supported import surface only.

- [x] Split the `clients` module into scope-focused files.
  - Goal: make client behavior discoverable by file name instead of requiring
    maintainers to scan large sync and async catch-all modules.
  - [x] Create `glpi_python_client.clients.v2` as the internal v2 implementation
    package.
  - [x] Group deterministic helpers under `glpi_python_client.clients.v2.common`
    with focused modules for `client_config`, `constants`, `request_http`,
    `ticket_search`, `response_payloads`, `payloads`, `filters`, and `errors`.
  - [x] Group synchronous endpoint behavior under
    `glpi_python_client.clients.v2.sync` with `transport`, `tickets`,
    `timeline`, `documents`, `team`, `directory`, and `api`.
  - [x] Group asynchronous endpoint behavior under
    `glpi_python_client.clients.v2.async_` with matching modules while keeping
    `asyncio.to_thread(...)` at the blocking request and v1-session boundaries.
  - [x] Keep `clients._shared` as the only compatibility helper export;
    reference sync and async mixins directly from
    `glpi_python_client.clients.v2.sync` and
    `glpi_python_client.clients.v2.async_`.
  - [x] Run the focused clients tests, package unit tests, Ruff, mypy, Sphinx,
    build, and high-confidence vulture after the layout split.
  - [x] Re-ran the live integration suite after the DNS issue was fixed.

- [x] Split the `content.records` module into scope-focused files.
  - Goal: make raw GLPI payload parsing discoverable by filename instead of
    grouping every model parser and helper in one large file.
  - [x] Keep `glpi_python_client.content.records` as the compatibility import
    path.
  - [x] Group shared parsing helpers under `records.core` with `normalization`,
    `scalars`, `references`, and `document_links`.
  - [x] Group model-specific parsers under `records.parsers` with `tickets`,
    `timeline`, `documents`, `team`, and `directory`.
  - [x] Run content tests, package unit tests, Ruff, mypy, Sphinx, build, and
    high-confidence vulture after the layout split.

## Phase 4: Documentation And Release Notes

- [x] Update `README.md` quick-start examples after signature changes.
- [x] Update Sphinx user guide and API reference after signature changes.
- [x] Update `docs/development.md` package layout names so they match the current
  package structure under `glpi_python_client/clients`, `content`, and `models`.
- [x] Add a changelog entry for public API changes, bug fixes, and any new
  compatibility notes.
- [x] Document the `skills/` directory distribution policy.
  - Decision: keep `skills/` as source-tree contributor material included in the
    source distribution but not in the installed runtime wheel.

## Phase 5: Validation Checklist

Run these checks before considering the plan complete:

- [x] `python -m pytest -q`
- [x] `python -m ruff check .`
- [x] `python -m mypy glpi_python_client`
- [x] `python -m sphinx -W --keep-going -b html docs docs/_build/html`
- [x] `python -m build`
- [x] `python -m vulture glpi_python_client --min-confidence 80`
  - Note: the default 60% confidence scan reports expected false positives for
    public library entry points and Pydantic fields; the higher-confidence pass
    is clean after removing one unused private helper.

## Progress Log

- 2026-05-13: Completed the second-level internal package organization by
  grouping shared v2 helpers under `glpi_python_client.clients.v2.common`,
  grouping execution-model code under `glpi_python_client.clients.v2.sync` and
  `glpi_python_client.clients.v2.async_`, grouping shared record parsers under
  `glpi_python_client.content.records.core`, and grouping model-specific
  parsers under `glpi_python_client.content.records.parsers`. Validation passed
  with focused clients/content Ruff checks and focused clients/content tests.
- 2026-05-13: Implemented the concrete clients-module cleanup decisions: added
  a public client method inventory, moved provisioning methods into the concrete
  sync and async clients, deleted the provisioning mixin modules and stale mixin
  memory notes, extracted shared v2 client resource setup, fixed `from_env()` so
  explicit `None` clears optional environment values, removed the unused
  `AsyncGlpiClient(batch_size=...)` constructor argument, replaced the MRO test
  with public behavior coverage, and updated the changelog. Validation passed
  with focused client tests, the full test suite, Ruff, mypy, Sphinx docs,
  package build, and the high-confidence vulture scan.
- 2026-05-13: Completed the scope-focused clients layout split by moving v2
  helpers and sync/async endpoint behavior under
  `glpi_python_client.clients.v2`; `clients._shared` remains as the narrow
  compatibility export, while mixins are used directly from
  `clients.v2.sync` and `clients.v2.async_`. Validation passed with focused
  client tests, package unit tests, Ruff, mypy, Sphinx docs, package build,
  and the high-confidence vulture scan. The live integration suite now passes
  again after the DNS issue was fixed.
- 2026-05-13: Completed the scope-focused content record layout split by
  turning `glpi_python_client.content.records` into a compatibility package and
  moving model parsers plus shared parsing helpers into focused modules.
  Validation passed with content tests, package unit tests, Ruff, mypy, Sphinx
  docs, package build, and the high-confidence vulture scan.
- 2026-05-13: Reduced another sync/async duplication slice by centralizing
  low-level request wrapper behavior and ticket search pagination helpers in
  `glpi_python_client.clients._shared`; added async coverage for ticket search;
  `python -m ruff check .`, `python -m mypy glpi_python_client`, and
  `python -m pytest -q` all pass.
- 2026-05-13: Reduced another low-risk sync/async duplication slice by
  centralizing mutation/provisioning response handling and upload preparation in
  `glpi_python_client.clients._shared`; added coverage for followup/solution ID
  fallback keys and v1-backed document upload; `python -m pytest -q`,
  `python -m ruff check .`, and `python -m mypy glpi_python_client` all pass.
- 2026-05-12: Initial health review completed. Test suite and docs build pass;
  Ruff and mypy currently fail; async MRO, v1 close behavior, and public
  argument contracts were identified as the first cleanup targets.
- 2026-05-12: Completed the first cleanup pass: fixed async MRO, fixed v1 close
  cleanup, made `glpi_api_url` mandatory on sync and async constructors, restored
  Ruff and mypy to clean status, and added regression tests for the corrected
  behavior.
- 2026-05-12: Full validation passed with `python -m pytest -q`,
  `python -m ruff check .`, `python -m mypy glpi_python_client`,
  `python -m sphinx -W --keep-going -b html docs docs/_build/html`, and
  `python -m build`.
- 2026-05-12: Completed the second public API/design pass: credential and v1
  cross-field validation are documented and tested, public ID arguments use
  `str | int`, create/upload requirements are enforced at operation boundaries,
  location filters are escaped, document metadata enrichment can be disabled and
  logs skipped lookups, internal exports/API docs are trimmed, and live
  integration tests were aligned with GLPI v2 user search and team-role values.
- 2026-05-12: Final validation passed with `python -m pytest -q`,
  `python -m ruff check .`, `python -m mypy glpi_python_client`,
  `python -m sphinx -W --keep-going -b html docs docs/_build/html`, and
  `python -m build`.
- 2026-05-12: Reduced another low-risk slice of sync/async duplication by
  centralizing shared v2 client environment parsing and several common
  response-normalization helpers in `glpi_python_client.clients._shared`.
- 2026-05-12: Installed `vulture`, removed one unused private helper from
  `content.records`, and documented the project dead-code scan at
  `--min-confidence 80` to avoid public-API and Pydantic false positives.
- 2026-05-12: Post-refactor validation passed with `python -m pytest -q`
  (`105 passed, 6 skipped`), `python -m ruff check .`,
  `python -m mypy glpi_python_client`,
  `python -m sphinx -W --keep-going -b html docs docs/_build/html`,
  `python -m build`, and
  `python -m vulture glpi_python_client --min-confidence 80`.
