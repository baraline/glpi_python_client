# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Fixed

- **The unit test suite was published inside the wheel and the sdist.** Both
  artefacts carried 56 test modules, so every install shipped the project's
  own tests into the consuming environment. `[tool.hatch.build] exclude` now
  drops `tests/` and `conftest.py`, taking the wheel from 180 entries to 126
  and the sdist from 204 to 150. Nothing a downstream consumer imports was
  removed: `glpi_python_client.testing` — the documented factories, fixtures
  and fake responses — still ships in full, and the package now imports
  cleanly in an environment with no `pytest` installed.

- **A `Major` priority ticket made the whole search fail.** GLPI's priority
  scale has six levels; the published contract advertises five, and
  `GlpiPriority` followed the contract. Since `GetTicket.priority` is typed
  with that enum and validation runs per record, a single escalated ticket
  anywhere in a result set raised `ValidationError` and took the entire
  query down with it — most likely to bite exactly the reporting queries
  that filter on high priority. `GlpiPriority.MAJOR = 6` is now defined.
  The five existing members keep their identifiers, so stored filters are
  unaffected. `urgency` and `impact` genuinely do stop at 5 and now accept a
  value GLPI will never send, which is harmless in the direction that
  matters.

- **The statistics layer sent GLPI v1 field names to the v2 API, which
  silently ignored them and returned unfiltered results.** v2 drops a
  `filter=` conjunct whose field it does not recognise, honours the rest,
  and answers 200/206 with no error — so the aggregations narrowed by date
  and looked plausible while ignoring the user and entity selection
  entirely. Measured against a live GLPI 11 instance,
  `get_user_activity` reported `tickets_as_technician == tickets_as_recipient
  == 963` — the window's *total* ticket count — for every user regardless of
  who they were. Corrected:
  - `entities_id==N` → `entity.id==N` (v2 types `entity` as an object).
  - `users_id_lastupdater==N` → `user_editor.id==N`.
  - `users_id_requester==N` (as `user_recipient_id`) → `user_recipient.id==N`,
    which is what that parameter's *name* has always meant. Note the v2
    `user_recipient` field is `users_id_recipient` — who *recorded* the
    ticket — not the requester link; the two are different people.
  - `users_id_assign` / `users_id_requester` (as `user_id`) have **no v2
    equivalent at all**: the v2 `team` array cannot be joined by the RSQL
    engine (the four contract-declared subfields answer HTTP 500 and every
    other spelling is silently ignored — 19 spellings were tested). These
    now resolve through the legacy v1 search engine, whose searchOption 5
    (`Technicien`) and 4 (`Demandeur`) map exactly onto the
    `glpi_tickets_users` link types, and which fails **loudly** (HTTP 400)
    on an unknown field instead of silently returning everything.
- **`rsql_any_filter` produced an unparenthesised OR group**, and RSQL binds
  `;` (AND) tighter than `,` (OR). `get_ticket_statistics(entity_name=...)`
  matching several entities emitted `date;e==1,e==2`, which the server reads
  as `(date AND e==1) OR e==2` — the date window stopped applying to every
  entity after the first. Measured live: 16,245 tickets returned where the
  correct answer was 1,552. OR groups are now wrapped in parentheses.
- **v2 ticket searches counted soft-deleted tickets.** The v2 search includes
  trashed tickets by default while v1 excludes them (59,690 live + 258
  trashed = 59,948), so every aggregation was inflated by the trash bin — for
  one user 92% of matches were deleted tickets. All v2 ticket queries in the
  statistics layer now pin `is_deleted==false`.
- Actor identifiers are validated before reaching the v1 search, which fails
  *open* rather than rejecting bad input: `equals 0` matched 20,905 tickets
  (a LEFT-JOIN-NULL "has no actor" match), an empty value matched the entire
  baseline, and a non-numeric value returned the same arbitrary 3 rows
  whatever the string. A non-positive or non-`int` id now raises
  `GlpiValidationError`.
- **The per-ticket task fan-out is replaced by one bulk sweep.** The v2 API
  publishes tasks only under `/Assistance/Ticket/{id}/Timeline/Task`, so
  aggregating N tickets cost N requests. The v1 `TicketTask` *collection*
  returns whole rows including `tickets_id`, paged 1000 at a time, so the
  same aggregate now costs one page per 1000 tasks created since the window
  opened. Measured live on a 120-ticket set: **120 requests / 11.7 s -> 2
  requests / 0.4 s**, with `ticket_count`, `task_count`, `total_duration`,
  `duration_by_ticket` and `duration_by_user` all byte-identical between the
  two paths. Below 25 tickets the per-ticket path is cheaper and is kept, so
  clients without a v1 session are unaffected.

  Note v1 `search/TicketTask` is *not* usable for this: its searchOptions
  expose the task id, content, category, date, privacy, technician, duration
  and state, but no parent ticket id, so results cannot be attributed back
  to a ticket. The plain collection endpoint is what carries `tickets_id`.

- `get_user_activity` walks the date window **once** for all users instead of
  twice per user. Combined with the corrected filters this took one user over
  90 days from **979 requests / 120 s to 9 requests / 5.1 s**, verified live.

  Actor-based statistics now require the legacy v1 session (`v1_base_url` +
  `v1_user_token`) and raise `RuntimeError` naming the missing options when
  it is absent, rather than returning a wrong number.

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
- The integration suite is runnable end-to-end again. Two defects, both in
  `integration_tests/` only (no library code involved):
  - `test_iter_search_tickets_multi_page` walked *every* matching ticket in
    batches of 3 with no upper bound — it was the only one of the suite's
    seven `iter_search` loops missing a `break`. Against a real instance
    (59,879 matching tickets) that is ~19,960 requests and several hours,
    which stalled the whole suite. It now stops after 3 pages and asserts
    that ids do not repeat across pages, which actually verifies that the
    `start` offset advances — the old unbounded loop asserted only
    `isinstance(collected, list)` and so could not have detected a stuck
    offset.
  - The three GLPI Fields plugin tests failed rather than skipped when the
    plugin is not installed. `_skip_when_no_v1` only checked that v1
    *credentials were configured*, never that the *plugin existed*; an
    absent plugin makes GLPI reject the `PluginFieldsContainer` itemtype
    with a 400 rather than return an empty list. A new `fields_containers`
    fixture skips on exactly that signature (400 +
    `ERROR_RESOURCE_NOT_FOUND_NOR_COMMONDBTM`) and re-raises anything else.
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

- **`AsyncGlpiClient` now performs real non-blocking I/O.** It was a facade
  that wrapped each synchronous method in `asyncio.to_thread`, so "async"
  meant "blocking call on a worker thread". It is now genuinely
  asynchronous, built on `httpx.AsyncClient`, with no thread pool and no
  executor. The `executor` constructor keyword is gone, as is
  `AsyncBridge`.
  - The two clients are now one codebase. `glpi_python_client/_async/` is
    hand-written and `glpi_python_client/_sync/` is generated from it by
    `unasync_build.py`, committed, and diffed in CI. Endpoint logic exists
    exactly once, so the two surfaces cannot drift.
  - This deletes the six hand-written async override modules the bridge
    forced into existence — including the 500-line `_statistics_async.py`,
    which duplicated the most intricate logic in the package with no test
    asserting the two copies agreed.
  - Aggregating helpers keep their concurrency through a shared `gather`
    helper that is `asyncio.gather` on the async surface and sequential
    evaluation on the generated one, written once at the call site.
  - **Public imports are unchanged**: `from glpi_python_client import
    GlpiClient, AsyncGlpiClient` still works. Code importing private
    module paths (`glpi_python_client.clients.*`, `glpi_python_client.auth.*`)
    must add the tree segment, e.g.
    `glpi_python_client._sync.clients.commons._transport`.
- **Breaking: the HTTP transport moved from `requests` to `httpx`.**
  `requests` and `urllib3` are no longer dependencies. The v2 transport, the
  legacy v1 session, and the OAuth token manager were swapped together in a
  single change because they share `_http.py`; splitting them would have left
  the shared code validated only by tests exercising the old transport.
  Behaviour is preserved, which took three deliberate corrections where the
  two libraries disagree and the difference is silent:
  - **Query parameters with a `None` value are dropped**, as `requests` did.
    `httpx` encodes them as a valueless `key=`, and GLPI treats an empty
    filter or search value as *match everything* — so the swap would have
    silently widened queries rather than leaving them unconstrained.
  - **`bytes` and `bool` parameter values keep their previous rendering**
    (`b"x"` → `x`, `True` → `True`). `httpx` would emit the Python repr
    `b'x'` and a lowercase `true`.
  - **Redirects are still followed.** `requests` follows them by default and
    `httpx` does not, so a followed redirect would have started surfacing as
    a bare 3xx response.
- **Breaking: network-level faults now raise `GlpiTransportError`** (or its
  `GlpiTimeoutError` subclass) instead of propagating the HTTP library's own
  exception. This completes the promise the previous release documented:
  catching `GlpiError` is now sufficient for the library's whole failure
  surface, and you never need to import the HTTP library. The originating
  exception is attached as `__cause__`. Code doing
  `except requests.RequestException` should now catch `GlpiTransportError`.
  Note it does *not* inherit `ValueError` — nothing was passed in wrongly and
  no value came back.
  - The retry predicates were retargeted onto this library-owned type in the
    same change. This is the failure mode that made the swap risky: the
    exception trees of the two libraries are completely disjoint, so a
    predicate left naming the old one stops matching and **every retry
    silently disappears** — no error, no warning, and a green test suite.
    Naming a type the library itself raises makes that impossible to
    reintroduce. A mutation test confirms the suite catches it: reverting the
    predicate fails 7 tests across all three transports.
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

### Performance

- **`sniffio` is now a dependency, and the async client is ~2.6x faster at
  wide fan-out because of it.** `httpcore` decides whether it is running
  under asyncio or trio by probing for `sniffio` on every async request,
  falling back to `"asyncio"` when the import fails. Nothing in the
  dependency chain required it — `httpx` pulls in `anyio`, and `anyio` 4.14
  dropped `sniffio` — so a fresh install had no `sniffio`, and because
  Python never caches a failed import, every single request re-walked
  `sys.path` doing filesystem stats. Measured against a local server with
  50 ms latency, a fan-out of 128 took **3354 ms without `sniffio` and
  1304 ms with it**. `pip check` reports no broken requirements either way,
  which is why this went unnoticed: nothing declares the package, nothing
  imports it, and the only symptom is that every request is slower.

- **Bounding a wide fan-out is now a documented requirement, not a
  suggestion.** `httpcore` rescans its entire connection pool on every
  request assignment, calling `has_expired()` per connection — profiled at
  9040 such calls for a 64-request fan-out. The cost is quadratic in the
  width of the fan-out and it saturates the event loop, so server-observed
  concurrency *falls* as the fan-out widens. Raising `httpx.Limits` does not
  help. At a fan-out of 16 against a 50 ms server, an unbounded
  `gather` took 350 ms while the same work capped at 16 with an
  `asyncio.Semaphore` took 108 ms. See "Bounding concurrency" in the user
  guide. This is a property of `httpx` 0.28 / `httpcore` 1.0.9, which are
  the current releases; there is no version to upgrade to.

### Documentation

- **The documentation still described the deleted bridge**, in the places
  users actually read: the README, the user guide, the API reference, the
  package docstring, and two skills all said `AsyncGlpiClient` wraps each
  synchronous method into a coroutine dispatched to a worker thread via
  `asyncio.to_thread`. None of that has been true since the codegen
  rewrite. The worst of it was live API: the user guide's *Custom thread
  pools* section and step 8 of `glpi-client-setup` documented an
  `executor=` constructor argument that no longer exists, so anyone
  copying either example got a `TypeError`. That section is now
  *Bounding concurrency* and shows an `asyncio.Semaphore`, which is what
  actually bounds a fan-out now.
- **Fourteen docstring cross-references pointed at modules the rewrite had
  renamed or deleted** (`clients.async_client`, `clients.sync_client`,
  `custom._ticket_context_async`). Nothing caught them: Sphinx runs with
  `nitpicky` off, so an unresolvable target renders as plain text rather
  than failing the build, and these private modules are not autodoc'd in
  the first place. `tests/test_docstring_references.py` now resolves every
  qualified reference in the package against the live modules.
- **The generated sync tree documented itself in terms of the async one.**
  unasync repoints imports, where `_async` is its own NAME token, but a
  dotted path inside a docstring is a single string token and passes
  through untouched — so 47 cross-references in the shipped sync client
  pointed into `_async/`. The diff gate is blind to this for the same
  reason it is blind to a token collision: the omission is deterministic,
  so regeneration reproduces it and the diff stays clean. `unasync_build`
  now repoints the qualified prefix, and a test asserts the generated tree
  never names `_async` at all.
- `TicketContextMixin` claimed its five calls ran sequentially and that an
  async override fanned them out, contradicting both the code and its own
  method docstring. The development guide still described the deleted
  `_ticket_context_async.py` / `_statistics_async.py` and the retired
  `test_parity.py` / `test_async_selfcall_guard.py` suites.
- The `requests` intersphinx mapping is removed; it survived the transport
  swap and made every docs build fetch an inventory nothing referenced.

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
