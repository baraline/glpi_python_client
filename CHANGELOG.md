# Changelog

## Unreleased

- Made `glpi_api_url` a required keyword-only constructor argument for
  `GlpiClient` and `AsyncGlpiClient`, while keeping explicit missing-URL
  validation in `from_env()`.
- Removed the unused `AsyncGlpiClient(batch_size=...)` constructor argument;
  per-call `search_ticket_records(batch_size=...)` remains supported.
- Updated `from_env()` so explicit `None` overrides clear optional values read
  from the environment.
- Moved user, location, and document provisioning methods into the concrete
  sync and async clients, removing the internal provisioning mixins.
- Reorganized the internal v2 client implementation into
  `clients.v2.common`, `clients.v2.sync`, and `clients.v2.async_`, keeping the
  compatibility exports stable while making execution-model boundaries explicit.
- Removed the unused top-level `clients.api` and `clients.async_api` mixin shim
  modules; internal code now imports the v2 sync and async mixins directly.
- Reorganized raw GLPI record parsing into `content.records.core` and
  `content.records.parsers`, while keeping `content.records` as the
  compatibility import package.
- Fixed async client method resolution so provisioning methods use the async
  transport implementation instead of the provisioning stub.
- Ensured `GLPIV1Session.close()` releases its underlying HTTP session even
  when no v1 session token was initialized.
- Cleaned Ruff and mypy issues found during the project health review.
- Rejected partial legacy v1 document configuration when only `v1_base_url` or
  only `v1_user_token` is supplied.
- Allowed public client methods to accept GLPI identifiers as `str` or `int`.
- Added operation-level validation for ticket and location creation while
  keeping models usable for both input and fetched records.
- Escaped user text in location search filters and skipped blank location
  searches.
- Added optional document metadata enrichment control and warnings for skipped
  metadata lookups.
- Trimmed internal mixins and underscore helpers from package `__all__` exports.
- Aligned live integration tests with GLPI v2 user ID filters and team-member
  role values.

## 0.1.0 - 2026-05-12

- Initial standalone package structure.
- Added typed GLPI client, models, packaging metadata, documentation, and tests.
- Exposed the canonical `glpi_python_client` import package.
