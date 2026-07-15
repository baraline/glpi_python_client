"""Structural guard against the async bridge's self-call trap.

``AsyncBridge`` wraps every public sync method into a coroutine. A sync
body running inside a worker thread that calls a sibling *public* method
through ``self`` therefore receives a coroutine object, not data: the call
is silently dropped (``RuntimeWarning: coroutine ... was never awaited``).

Any public method that transitively reaches a public method through
``self`` must be given a hand-written async override on
``AsyncGlpiClient``. This test enforces that rule so the bug class cannot
be reintroduced by a future endpoint.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

from glpi_python_client import AsyncGlpiClient, GlpiClient

# Lifecycle helpers differ between the surfaces on purpose.
_EXCLUDED = {"from_env", "close"}


def _public_names(cls: type) -> set[str]:
    """Return the public callable names exposed by ``cls``."""

    return {
        name
        for name, _ in inspect.getmembers(cls, predicate=callable)
        if not name.startswith("_") and name not in _EXCLUDED
    }


def _self_call_map(cls: type) -> dict[str, set[str]]:
    """Map every method of ``cls`` to the ``self.X()`` names it calls."""

    out: dict[str, set[str]] = {}
    for klass in cls.__mro__:
        if klass is object:
            continue
        for name, member in vars(klass).items():
            if name in out:
                continue
            func = member
            if isinstance(func, (classmethod, staticmethod)):
                func = func.__func__
            if not inspect.isfunction(func):
                continue
            try:
                tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
            except (OSError, TypeError, SyntaxError):  # pragma: no cover
                continue
            calls: set[str] = set()
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "self"
                ):
                    calls.add(node.func.attr)
            out[name] = calls
    return out


def _reaches_public(
    name: str,
    call_map: dict[str, set[str]],
    public: set[str],
    seen: set[str] | None = None,
) -> bool:
    """Return whether ``name`` reaches a public method through ``self``.

    Recurses through private helpers, which is what catches
    ``create_kb_article`` -> ``_apply_category_fallback`` ->
    ``set_kb_article_categories``.
    """

    if seen is None:
        seen = set()
    if name in seen:
        return False
    seen.add(name)
    for callee in call_map.get(name, set()):
        if callee in public:
            return True
        if callee.startswith("_") and _reaches_public(callee, call_map, public, seen):
            return True
    return False


def _is_real_async_override(member: object) -> bool:
    """Return whether ``member`` is a hand-written async override.

    The bridge builds its wrappers with ``functools.wraps``, so a
    bridge-generated coroutine carries ``__wrapped__`` while a real
    override does not.
    """

    if not (inspect.iscoroutinefunction(member) or inspect.isasyncgenfunction(member)):
        return False
    return not hasattr(member, "__wrapped__")


def _offenders() -> list[str]:
    """Return public methods that self-call but lack an async override."""

    public = _public_names(GlpiClient)
    call_map = _self_call_map(GlpiClient)
    return sorted(
        name
        for name in public
        if _reaches_public(name, call_map, public)
        and not _is_real_async_override(getattr(AsyncGlpiClient, name))
    )


def test_no_new_self_call_offenders() -> None:
    """No public method may self-call without a hand-written async override."""

    assert _offenders() == [], (
        f"These public methods call a public method through self with no async "
        f"override, so AsyncGlpiClient will silently drop those calls: "
        f"{_offenders()}. Add an async override mixin (see "
        "clients/custom/_statistics_async.py) and register it in "
        "clients/async_client.py before the sync mixin."
    )


def test_guard_detects_the_covered_methods() -> None:
    """The guard must recognise the existing overrides as valid.

    Without this, a guard that classified every method as covered would
    pass ``test_no_new_self_call_offenders`` vacuously.
    """

    for name in ("get_ticket_context", "get_task_statistics", "iter_search_tickets"):
        assert _is_real_async_override(getattr(AsyncGlpiClient, name)), (
            f"{name} should be a hand-written async override"
        )
    assert not _is_real_async_override(AsyncGlpiClient.get_ticket), (
        "get_ticket should be bridge-generated, not a hand-written override"
    )


def test_reaches_public_detects_transitive_and_direct_self_calls() -> None:
    """Pin ``_reaches_public`` against a synthetic call map.

    ``test_no_new_self_call_offenders`` now asserts ``_offenders() == []``.
    That assertion passes both when every real offender has an async
    override *and* when ``_reaches_public`` has regressed to returning
    ``False`` for everything — the two cases are indistinguishable from the
    assertion alone. The previous non-empty ``_KNOWN_UNCOVERED`` constant
    protected against that regression by accident, since a broken detector
    would drop the known offenders out of ``_offenders()`` and fail the
    equality check; emptying it removed that safety net.

    This test replaces it with a direct, synthetic check of the detection
    logic itself, independent of whatever offenders exist on the real
    client today. It fixes a call map shaped like the historical
    ``create_kb_article`` bug — a public method reaching another public
    method only transitively, through a private helper — and a call map
    that never reaches anything public, and asserts ``_reaches_public``
    still tells them apart.
    """

    public = {"create_thing", "set_thing_categories", "isolated_public"}
    call_map: dict[str, set[str]] = {
        # Mirrors create_kb_article -> _apply_category_fallback ->
        # set_kb_article_categories: the public caller only reaches the
        # public callee transitively, through a private helper.
        "create_thing": {"_apply_fallback"},
        "_apply_fallback": {"set_thing_categories"},
        "set_thing_categories": set(),
        # A public method that only ever touches private helpers which
        # themselves reach nothing public must not be flagged.
        "isolated_public": {"_do_local_work"},
        "_do_local_work": {"_do_more_local_work"},
        "_do_more_local_work": set(),
    }

    assert _reaches_public("create_thing", call_map, public) is True, (
        "a public method reaching a public method through a private helper "
        "must be detected"
    )
    assert _reaches_public("isolated_public", call_map, public) is False, (
        "a public method whose private helpers reach nothing public must not be flagged"
    )
