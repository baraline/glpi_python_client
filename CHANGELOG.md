# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Fixed

- `GLPITokenManager._refresh_access_token`'s retry decorator no longer
  retries a `GlpiServerError` from its fall-through to the nested
  `_acquire_token()` call. That nested call already carries its own
  independent 3-attempt retry decorator for `GlpiServerError`, so the
  outer decorator retrying it too meant a persistent 5xx during token
  refresh cost 3 (outer attempts) × (1 refresh POST + 3 nested acquire
  POSTs) = 12 POST requests and ~33s of `wait_fixed(3)` sleep, instead of
  the 3 attempts the retry configuration alone would suggest. The outer
  decorator now only retries `requests.RequestException` (a genuine
  network fault on the refresh POST itself), which is not covered by the
  nested call at all. A persistent 5xx now costs exactly 1 refresh POST +
  3 nested acquire POSTs = 4 POST requests. A persistent 401 (2 POSTs) and
  a network error on the refresh POST (3 POSTs) are unaffected.
- `AsyncGlpiClient.create_kb_article` / `update_kb_article` no longer
  silently drop `categories`. Both methods called the public
  `set_kb_article_categories` through `self` from inside a synchronous
  method body; `AsyncBridge.__init_subclass__` wraps every public sync
  method into a coroutine, so that call returned an un-awaited coroutine
  instead of performing the write. The article was created (or updated)
  successfully, a valid id was returned, and no exception was raised —
  the category assignment simply never happened. Fixed with hand-written
  async overrides in `_article_async.py` that strip `categories` from the
  v2 body, run the v2 write in a worker thread, and apply the category
  fallback through an awaited call.
- `AsyncGlpiClient.get_ticket_custom_fields` / `set_ticket_custom_fields`
  raised `TypeError: 'coroutine' object is not iterable` and were
  unusable. Same root cause as above: a sync method reaching a sibling
  public method through `self` received a coroutine instead of a result.
  Fixed with hand-written async overrides in `_fields_async.py`.
- `parse_optional_env_int` (environment/config parsing) and
  `StatisticsMixin._resolve_window` (the date-window helper behind
  `get_ticket_statistics` / `get_task_durations` / `get_user_activity`)
  no longer let a malformed value escape as a bare stdlib `ValueError`
  from `int()` / `date.fromisoformat()` (e.g. `GLPI_TIMEOUT=abc` or
  `get_ticket_statistics(start_date="2026-13-45")`). Both now raise
  `GlpiValidationError`, chaining the original error via `from` rather
  than swallowing it. Non-breaking: `GlpiValidationError` inherits
  `ValueError`, so `except ValueError` still catches it.

### Added

- `glpi_python_client/clients/tests/test_async_selfcall_guard.py`: a
  structural AST guard that fails the suite if any public method on
  `GlpiClient` transitively reaches another public method through a
  literal `self.name(...)` call (directly, or via a private helper)
  without a corresponding hand-written async override on
  `AsyncGlpiClient`. This prevents the same bug class — silent data loss
  or a `TypeError` at call time, depending on how the dropped coroutine is
  used — from being reintroduced by a future endpoint.
- A public exception hierarchy, exported from the package root:
  `GlpiError`, `GlpiTransportError`, `GlpiTimeoutError`, `GlpiStatusError`,
  `GlpiAuthError`, `GlpiNotFoundError`, `GlpiServerError`,
  `GlpiValidationError` and `GlpiProtocolError`. `GlpiStatusError` and its
  subclasses carry `.status_code`, `.url` and `.response_text`. A GLPI 404
  and a bad argument were previously both a bare `ValueError` and could not
  be told apart.
- `FakeResponse` (in the public `glpi_python_client.testing` module) gained
  a `url` attribute.
- A user-guide "Error handling" section documenting the exception
  hierarchy and the retry behaviour for both the transport layer and OAuth
  token acquisition/refresh.

### Changed

- **Breaking:** a persistent 5xx now raises `GlpiServerError` instead of
  `tenacity.RetryError`. The retry decorators gained `reraise=True`. Code
  doing `except tenacity.RetryError` and digging out
  `.last_attempt.exception()` should now catch `GlpiServerError` directly.
- **Breaking:** unexpected HTTP statuses raise a `GlpiStatusError` subclass;
  rejected arguments and configuration raise `GlpiValidationError`; 2xx
  responses with an unusable body raise `GlpiProtocolError`. All three
  inherit `ValueError`, so existing `except ValueError` handlers keep
  working.
- **Breaking:** a non-2xx OAuth token response raises `GlpiAuthError` (401/403)
  or `GlpiServerError` (5xx). The token retry decorators had no `retry=`
  predicate and therefore retried every failure, including a rejected
  credential; a wrong `client_secret` cost 3 attempts and 6 seconds. OAuth
  4xx is now final, matching the rest of the library. OAuth 5xx is still
  retried.
- **Breaking:** the private `glpi_python_client.clients.commons._errors`
  module and its `remote_error_message` helper are removed. It had no
  library call sites, and `reraise=True` leaves it nothing to unwrap.

### Unchanged (deliberately)

- Retry semantics: 5xx retried 3 times with a 3-second fixed wait, 4xx never
  retried.
- Tolerant search endpoints still return `[]` rather than raising on a 4xx.
- The `TypeError` sites in environment parsing and the `RuntimeError` sites
  for closed clients, missing v1 sessions and partial KB failures still
  raise those types. `GlpiValidationError` inherits `ValueError`, not
  `TypeError`, so converting them would break `except TypeError` callers.
- The transport is still `requests`. Network faults (connection reset, DNS,
  timeout) still surface as `requests` exceptions; they become
  `GlpiTransportError` / `GlpiTimeoutError` when the transport moves to
  httpx, with no change to the class names above.

### Notes

- Both fixed bugs shared one root cause: `AsyncBridge` wraps every public
  sync method into a coroutine, so a sync method body calling a sibling
  public method through `self` (rather than through a hand-written async
  override) silently receives a coroutine instead of the real return
  value.
- This is a documentation-only release note; **no version was released**
  from this branch. The next release is planned as 0.4.0, an httpx +
  unasync rewrite that removes `AsyncBridge` entirely, making this class
  of bug structurally impossible rather than merely guarded against.
