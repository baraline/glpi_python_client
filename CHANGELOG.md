# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 0.5.0 — 2026-09-08

### Fixed

- **Deeply nested HTML raised `RecursionError` while a model was being
  validated.** `markdownify` walks the parsed document recursively and
  spends about two CPython frames per nesting level, so roughly 494 levels
  exhausted the default 1000-frame limit — measured, and the same 494
  whether the nesting is `<div>`, `<p>`, `<blockquote>`, `<ul><li>` or
  `<table><tr><td>`, which is what identifies the cost as per-level. An
  unclosed tag counts too: `html.parser` does not auto-close `<p>` or
  `<li>`, so `"<p>" * 5000` really is 5000 levels.

  Because the converter was wired as a Pydantic `BeforeValidator`, the
  failure landed inside `model_validate` — that is, inside `get_ticket` —
  as a bare builtin from a library whose whole error surface is supposed
  to derive from `GlpiError`.

  `from_transport` now measures nesting first, with a flat non-recursive
  O(n) scan, and past `MAX_HTML_DEPTH` (200) strips tags instead of
  parsing. **It degrades, it never truncates, and it does not raise for
  depth**: every character the converting path would have produced also
  appears in the degraded rendering.

  Both halves were fuzzed against the real parser over 15000 documents,
  with zero under-counts, zero over-counts and zero text losses. Getting
  there took several rules that are not the obvious ones:

  - A closing tag pops by name or is ignored — `bs4` pops nothing when no
    element of that name is open, so `"<div></p>" * 600` really is 600
    deep where a naive counter says 1.
  - An attribute value may contain `<` and `>`, so
    `'<div title="</div>">' * 600` also measured 0 against a real 600
    until the scan learned to skip quoted values.
  - A quote opens a value only as the first character after the `=`,
    which is the parser's own rule, so `<p title=don't>` carries the
    value `don't`. Reading that apostrophe as a quote printed the opening
    tag verbatim at the reader — and an apostrophe needs no malice to
    reach a French ticket body.
  - `tagfind_tolerant` runs a tag *name* to whitespace, `/` or `>`, so
    `<style=>` is an element named `style=` and never enters raw-text
    mode; a self-closed `<script/>` does not either, because
    `parse_starttag` enters it only on the branch that is not
    self-closing. Reading either as raw text swallowed the rest of the
    document: `"<style=>" + "<div>" * 600` measured 1 level against a
    real 601 and raised.
  - A declaration is text on neither path only when it is closed. A
    `<!weird` left unterminated at end of input is flushed as character
    data when the parser closes, so dropping it lost the tail of a body.
  - An unclosed tag counts, a childless node still occupies a level, and
    a bogus comment swallows the tags inside it.
  - The degraded path had to be measured against the converting path
    construct by construct rather than reasoned about. Three answers came
    back the opposite way round: a `<script>`/`<style>` body is *kept*
    (`markdownify`'s `strip=` removes an element's markup and still walks
    its children), so is a `CDATA` body, and so is the inside of any
    `<!`/`<?` construct the parser could not resolve.

  What the degraded rendering does not reproduce, none of it prose: link
  targets and image alt text, fenced-block and `<pre>` indentation,
  `&nbsp;`-padded alignment, and a processing instruction's `<?`/`>`
  delimiters, which survive as literal text.

  Character references are resolved by the parser's rule rather than by
  `html.unescape`, which implements HTML5's longest-known-*prefix* rule
  and would rewrite a pasted URL: `?a=1&copyright=2` becomes
  `?a=1©right=2` under `unescape` and is left alone by the parser. A
  semicolon-less reference resolves only when its whole name is known.

  The ceiling is 200 rather than 492 because the budget is not 1000
  frames, it is whatever is left of the stack when conversion starts, and
  that belongs to the caller. Measured at the call site: 8 frames through
  the synchronous client, 16 through the asynchronous one, 37 from twenty
  nested awaits. The library's own contribution is negligible; an
  application converting from inside a request handler or a recursive
  walk is not. Converting a 200-level document peaks at a measured 403
  frames, so it stays safe until the caller's own stack passes roughly
  590 — and no document a human wrote nests 200 elements deep.

  **`sys.setrecursionlimit` was considered and rejected.** It is
  process-global state belonging to the application, not to a library the
  application imported; and past what the C stack can hold it converts a
  catchable `RecursionError` into a hard interpreter crash — on Windows,
  an access violation with no traceback. It moves the cliff and makes
  falling off it worse. The prohibition is asserted by
  `testing/tests/test_raise_site_audit.py` rather than left as a comment
  for the next person to weigh up again.

- **A body that used both spellings of `<br>` lost everything after the
  second one.** `<p>line1<br>line2</p><p>para2<br />line4</p>` converted
  to `line1  \nline2\n\npara2` — `line4` silently gone, no error, on the
  ordinary conversion path.

  The cause is in `beautifulsoup4` (measured on 4.14.3), not in
  `markdownify`. Its `html.parser` builder auto-closes a bare `<br>` and
  records the name in `already_closed_empty_element` so a later `</br>`
  can be ignored as redundant; when no `</br>` arrives the entry just
  stays. The next `<br />` reaches the builder as `handle_startendtag`,
  opens a real element and closes it itself — and that close finds the
  stale entry, treats the element as already closed, and leaves it open,
  so every following sibling becomes a child of the `<br>`.
  `markdownify`'s `convert_br` ignores an element's children, and the
  text is gone. `get_text` walks children, which is why the tree looks
  intact.

  Note the paragraph in the example: the two spellings need not be near
  each other, since a name once recorded poisons the rest of the
  document. `<img>` and `<hr>` are the other two converters that discard
  children and lost text the same way.

  `from_transport` now writes self-closing void tags bare before
  converting, which removes the `handle_startendtag` path where the
  asymmetry lives. Both spellings already built the same node, so nothing
  else moves: measured over 4000 fuzzed documents of each spelling alone,
  not one output changed, and over 4000 mixing them, 102 recovered text
  and none lost any. Only names in the void set are touched, and only in
  real tag position — a `<div/>`, a `<br />` inside an attribute value, a
  comment or a `<script>` body are all left alone.

- **`GlpiModel` now recognises validation aliases when it captures unknown
  keys.** `_capture_unknown_fields` runs before Pydantic resolves aliases
  and compared incoming keys against field *names* only, so an aliased key
  was diverted into `extra_payload` before its field could see it — HTTP
  200, no warning, and the value silently `None`. Latent until this
  release, which introduces the package's first alias.

### Added

- **`GlpiContentError`** — a new `GlpiError` leaf for a rich-text body
  that could not be converted, in either direction, with the underlying
  fault attached as `__cause__`. Exported from the package root and
  documented in the API reference.

  Content conversion previously sat outside the taxonomy altogether: a
  parser fault escaped `except GlpiError` and reached the caller as a bare
  builtin. The depth ceiling above means no ordinary input gets here, so
  this is the backstop — including for the outbound direction, where
  `markdown` has its own cliff at around 500 levels of list indentation.

  Unlike `GlpiStatusError`, `GlpiValidationError` and `GlpiProtocolError`
  it does **not** inherit `ValueError`. Those three carry it for
  compatibility with releases that raised bare `ValueError` at the same
  sites; there was never a `ValueError` at a conversion site, and a parser
  exhausting the stack is not a value the caller got wrong. Same reasoning
  as `GlpiTransportError`.

- **`content_html` on the read models**, holding the wire value verbatim:
  `GetTicket`, `GetFollowup`, `GetTicketTask`, `GetSolution`,
  `GetKBArticleRevision`, and `GetKBArticle` (which also gains
  `description_html`).

### Changed (breaking)

- **Read models convert to Markdown on first access instead of during
  validation.** `content` is now a `functools.cached_property` over
  `content_html`:

  ```python
  ticket = client.get_ticket(42)
  ticket.content_html   # '<p>Printer is <strong>offline</strong></p>'
  ticket.content        # 'Printer is **offline**'  (converted here, once)
  ```

  **Callers that read `.content` need no change.** The field carries the
  validation alias `content`, so a GLPI payload and a hand-written
  `GetTicket(content=...)` both still populate it, and `.content` still
  returns Markdown. What changes is *when*.

  Two things follow. A caller who wants only `id` and `date_mod` no longer
  pays HTML-to-Markdown on every record of every page. And a body that
  cannot be converted no longer takes its page-mates with it:
  `TransportMixin._resource_list` builds every item of a page in one
  comprehension, so one unconvertible record used to make the whole page
  unreadable — the failure is now scoped to the record whose body is
  actually read.

  Write models (`Post*`, `Patch*`) are deliberately unchanged: they keep
  the plain `content` field and convert eagerly, so a caller's own
  Markdown is still checked where it was supplied, and there is no list
  path on a write model to make lazy.

  What does break: `content` is no longer in `GetTicket.model_fields`, and
  `GetTicket(...).model_dump()` emits `content_html` holding HTML where it
  used to emit `content` holding Markdown (`by_alias=True` gives a dump
  keyed the way GLPI keys it).

  One sharp edge comes with the cache. Assigning to `content_html` after
  `.content` has been read leaves the stale Markdown in place, and so does
  `model_copy(update={"content_html": ...})` — and neither equality,
  `repr` nor any `model_dump` reveals it. Treat a read model as immutable
  once validated, or rebuild it through `model_validate`.

## 0.4.3 — 2026-08-13

### Changed (breaking)

- **`server_timezone` is now a required client argument** (`GLPI_SERVER_TIMEZONE`
  for `from_env`). It takes an IANA zone name — `"Europe/Paris"` — or a
  `tzinfo`.

  GLPI 11 sends most timestamps with the correct historical offset, but not
  all of them. Measured against a live instance: 19 of the 20 datetime fields
  across every resource are offset-bearing, and `KBArticle.revisions[].date`
  is not. One response therefore carries both kinds, and comparing them raises
  `TypeError: can't compare offset-naive and offset-aware datetimes` — sorting
  an article's revision history against the article's own dates was enough to
  trigger it.

  There is deliberately **no default**. Every candidate is wrong somewhere:
  against a Europe/Paris instance, assuming UTC shifts the affected timestamps
  by one or two hours *and stops raising*, turning a loud failure into a quiet
  wrong answer. An IANA name is preferred over a fixed offset because a name
  follows DST — the same instance emits both `+01:00` and `+02:00`.

  An offset already on the wire always wins over the configured zone, and a
  model built outside the client (no validation context) keeps its naive values
  rather than being stamped with a guess.

  Adds `tzdata` as a dependency on Windows, which ships no system timezone
  database; without it `zoneinfo` resolves on Linux CI and raises on a
  developer machine.

- **`changed_since` no longer assumes UTC.** An aware `datetime` now needs the
  server's timezone and raises `GlpiValidationError` without it:

  ```python
  window = changed_since(last_run, tz=client.server_timezone)
  ```

  The bound this builds is compared against a naive server-local column, so
  converting the caller's moment to UTC asked the server for a different one.
  A 09:33 Paris timestamp became a `07:33` filter. East of UTC that only
  re-reads a few hours on every sweep; west of it the bound moves *forward*
  and modifications are skipped outright — four hours in New York, seven in
  Los Angeles — and the size of the drift changes at each DST transition, so
  a sync that looks correct in January starts losing rows in March.

  The offset is now spent converting the value onto the server's clock and
  then dropped, which is what the model serialiser already does on the way
  out; the two halves had diverged by exactly the offset. Missing `tz` is
  refused rather than defaulted for the same reason `server_timezone` has no
  default: every guess is wrong somewhere, and being wrong here returns a
  short result set rather than an error.

  A `date`, an ISO string, or a naive `datetime` is unaffected and needs no
  `tz` — a naive value already means the server's clock.

- **Search endpoints now raise on a 4xx instead of returning `[]`.** The seven
  `search_*` helpers passed no `failure_message` to `_resource_list`, which
  skipped the status check entirely, so a 400, 401, 403 or 404 came back as an
  empty list — indistinguishable from a filter that legitimately matched
  nothing. (5xx already raised.) It composed badly with the batch iterators:
  they stop on a page shorter than `batch_size`, so a 403 on the first page
  ended the walk having yielded nothing and the caller saw a *successful*
  empty result. This reverses decision D2 of the 0.4.0 error work, which chose
  tolerance deliberately; the silent-empty failure mode has proved worse than
  the exception. An empty list now means the server said the result set is
  empty. **Callers that relied on `[]` after a permission error must catch
  `GlpiStatusError`.**

### Added

- **`PatchTicket.status`** — ticket status is writable after all, typed
  `GlpiTicketStatus | None`:

  ```python
  client.update_ticket(ticket_id, PatchTicket(status=GlpiTicketStatus.PENDING))
  ```

  The field had been excluded on the grounds that GLPI "manages the ticket
  lifecycle through dedicated timeline routes", which is what the contract
  says: it publishes `Ticket.status.id` as `readOnly: true`. Measured against
  a live GLPI 11 instance, that is wrong — `PATCH` with `{"status": 5}`
  answers 200 and the ticket moves. Same failure mode as the `Major` priority
  level the contract omits: observed server behaviour wins.

  It is declared on `PatchTicket` and **not** on `PostTicket`, because the two
  routes genuinely differ — `POST` with a status answers 201 and creates a
  *New* ticket, dropping the field. A create argument for it would have done
  nothing. `status_id` is likewise ignored; `status` is the spelling that
  works.

  The annotation is the enum rather than `int` deliberately. GLPI validates
  nothing here: `{"status": 99}` answers 200 and stores it, after which the
  API reports `{"id": 99, "name": "99"}`, the web form displays the ticket as
  *New*, and the ticket vanishes from the ticket list while remaining open in
  the database — only the history records the change. A typo like `55` for
  `5` would lose a ticket in silence, so this model is the only validation on
  the path. `GetTicket.status` stays the permissive `IdNameRef`, since a
  strict enum on the read side would fail a whole search over one bad row.

- **`glpi_python_client.rsql`** — public date builders for the v2 filter
  grammar: `created_between`, `date_window` and `changed_since`, all exported
  from the package root. The end-of-day detail on a window's upper bound is
  easy to get wrong and impossible to notice, since GLPI answers a malformed
  filter by ignoring it and returning the whole table.

- **`find_user_by_email(email)`** — resolves a person by address. It scans,
  because GLPI exposes addresses as the nested array `User.emails` and the v2
  filter engine cannot join a nested array. Narrow it with `rsql_filter` and
  cache the id; do not hand-roll an RSQL e-mail filter.

- **`stream_document_content(document_id, chunk_size=...)`** — yields a
  document body in chunks instead of buffering it whole, as
  `download_document_content` does. Upload still buffers.

- **Batch iterators for the four resources that lacked one**:
  `iter_search_kb_articles`, `iter_search_kb_categories`,
  `iter_search_documents` and `iter_search_locations`.

### Fixed

- **Every `datetime` write raised `TypeError`.** `model_to_payload` dumped in
  Pydantic's python mode, so a request body reached `json.dumps` still holding
  a live `datetime`. The failure landed at the encoder — after the model had
  validated and outside any transport stub — which is why the suite never saw
  it. The dump now runs in JSON mode.

- **GLPI discards the offset on every datetime it is sent, so aware values
  were written as the wrong moment.** Measured against a live Europe/Paris
  instance: `2026-08-01T12:30:00` written bare, as `...Z`, and with `+02:00`,
  `+09:00`, `-08:00` and `+14:00` all store 12:30 Paris. The server reads the
  naive prefix, interprets it in its own timezone, and throws the rest away —
  with a 200. It does parse the offset first, since `+99:99` answers HTTP 500,
  which is the worst combination: a malformed offset crashes, a well-formed
  wrong one is silent. `12:30-08:00` is 21:30 in Paris and landed nine hours
  early.

  An aware `datetime` is now converted onto the server's clock and the offset
  dropped, via a serialisation context mirroring the validation context used
  on the inbound half. Naive values are untouched — they already mean the
  server's clock — and no context means no conversion, so a model dumped
  outside the client is unchanged. This is the second half of the
  `server_timezone` contract above; `mode="json"` alone would have shipped
  writes wrong by up to twelve hours.

- **`get_ticket_statistics` silently truncated at 200 tickets**, on an
  instance whose own docstring records 59,690. It issued one `search_tickets`
  call with no paging loop, so every statistic was computed over whichever
  200 tickets came back first and reported as if it covered the corpus. The
  two entity and one user name-resolution sites had the same shape. All four
  now page through `iter_search_*`.

- **`from_transport` silently deleted text.** The HTML path was taken whenever
  the content held both `<` and `>`, so `"use the <Enter> key"` became
  `"use the  key"` — an unknown tag's markup is dropped and its empty body
  kept, removing the word with nothing left to show it was ever there.
  `"cmd </dev/null > out"` and `"if x<y then z>0"` lost text the same way. The
  decision is now made on the element *name*.

- **Fenced code blocks, tables and prose punctuation were mangled.** Without
  the `fenced_code` extension a fence rendered as inline `<code>`, which the
  GLPI web UI shows as one run-on line and which a later read wrote back as
  inline code — so a pasted log degraded further on every edit. Without
  `tables`, a table rendered as literal pipes. Inbound, `markdownify` escaped
  underscores and asterisks, so `snake_case` came back as `snake\_case` and
  accumulated a backslash on every read-modify-write cycle.

- **`_MAX_DATETIME` was naive, so `to_markdown()` raised on a mixed-awareness
  timeline.** Sorting events padded absent timestamps with `datetime.max`,
  which cannot be compared against the offset-bearing values GLPI sends. The
  sort key now normalises both sides to UTC. The live probe confirmed the
  mixed population is real, not hypothetical.

- **`require_response_int` rejected create responses GLPI actually returns.**
  A numeric-string id, an id nested under a `data` envelope, and a create that
  reports only a `Location` header all raised a protocol error over a
  perfectly usable identifier. It now probes top-level keys, then the
  envelope, then the header.

- **`sort="date_mod desc"` — the library's own documented example — is HTTP
  400.** Found while running the wire-format probe. The accepted syntax is
  `field:direction`; a bare `date_mod` is accepted but sorts *ascending*, and
  `order=` is ignored entirely.

- **Three client construction examples had `server_timezone` inserted twice
  and misindented**, by the sweep that added it. A repeated keyword argument
  is a `SyntaxError`, so those examples could not be copied at all. Two older
  documentation defects surfaced alongside them: three lines of expected
  output stranded inside a `code-block:: python` (they belong to the example
  above), and an import indented four spaces inside a three-space block. A new
  test compiles all 77 Python snippets in the skills, the guide and the
  README.

## 0.4.0 – 0.4.2

These three releases were tagged without the changelog ever being
sectioned, so their notes accumulated under a single `Unreleased`
heading. They are grouped here rather than split retroactively.

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

## Pre-0.4.0 notes

Kept for history. Written before the httpx and unasync rewrites, so the
status they describe is superseded by everything above — the transport is
no longer `requests`, and tolerant searches no longer swallow a 4xx.

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
