# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Fixed

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

### Added

- `glpi_python_client/clients/tests/test_async_selfcall_guard.py`: a
  structural AST guard that fails the suite if any public method on
  `GlpiClient` transitively reaches another public method through a
  literal `self.name(...)` call (directly, or via a private helper)
  without a corresponding hand-written async override on
  `AsyncGlpiClient`. This prevents the same bug class — silent data loss
  or a `TypeError` at call time, depending on how the dropped coroutine is
  used — from being reintroduced by a future endpoint.

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
